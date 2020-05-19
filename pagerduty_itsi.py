import sys
import json
import urllib2
import time
import re

from fnmatch import fnmatch

from splunk.clilib.bundle_paths import make_splunkhome_path

sys.path.append(make_splunkhome_path(['etc', 'apps', 'SA-ITOA', 'lib']))

from ITOA.itoa_config import get_supported_objects

# Updated for ITSI 4.4 - logging was changed for Python 2/3 integration
#from ITOA.setup_logging import setup_logging
import itsi_path
from itsi_py23 import _
from ITOA.setup_logging import logger

# updated for ITSI 4.0 - event actions were moved to EventGroup
#from itsi.event_management.sdk.eventing import Event
from itsi.event_management.sdk.grouping import EventGroup
#from custom_event_action_base to custom_group_action_base
#from itsi.event_management.sdk.custom_event_action_base import CustomEventActionBase
from itsi.event_management.sdk.custom_group_action_base import CustomGroupActionBase


def send_notification(payload):
    settings = payload.get('configuration')
    logger.info("Sending incident with settings %s" % settings)

    url = settings.get('integration_url_override')
    token = settings.get('token')

    if not url:
        url = settings.get('integration_url')

    # check if only the integration key was given
    if len(url) == 32:
        url = 'https://events.pagerduty.com/integration/' + url + "/enqueue"

   # Call functin to update payload for PagerDuty
    try:
        pd_body = modify_payload(payload)
    except:
        logger.error("Error modifying payload for PagerDuty")
        pd_body = payload

    body = json.dumps(pd_body,ensure_ascii=False).encode('utf8')
    logger.info('Calling url="%s" with body=%s' % (url, body))
    req = urllib2.Request(url, body, {"Content-Type": "application/json"})

    #Route external traffic through proxy, if set
    proxy = "<proxy>:<port>"
    proxies = {"https":"https://%s" % proxy}
    proxy_support = urllib2.ProxyHandler(proxies)
    opener = urllib2.build_opener(proxy_support)
    urllib2.install_opener(opener)

    try:
        res = urllib2.urlopen(req)
        body = res.read()
        logger.info("PagerDuty server responded with HTTP status=%d" % res.code)
        if res.code < 200 or res.code > 299:
            return False
    except urllib2.HTTPError, e:
        logger.error("Error sending message: %s (%s)" % (e, str(dir(e))))
        return False

    #event_id = payload['result']['event_id']
    #Note: For ITSI, use itsi_group_id instead of event_id
    event_id = payload['result']['itsi_group_id']
    session_key = payload['session_key']
    time.sleep(5) # wait 5 seconds for an incident to be created

    try:
        event = EventGroup(session_key)
        event.create_comment(event_id, "Successfully sent PagerDuty alert to %s" % url)
    except Exception as e:
        logger.error("Unknown error of type %s: %s" % (type(e).__name__, e))
        event.create_comment(event_id, "Unable to create PD incident for event ID %s: Unknown error: %s" % (event_id, e))

    return True


def modify_payload(payload):     #Function to modify JSON payload before sending to PagerDuty
    body_string = json.dumps(payload)
    body_load = json.loads(body_string)

    logger.info('Original payload="%s"' % (body_string))

    pd_body = {}

    #PagerDuty maps alert title to Core Splunk search_name; ITSI episode title is result.itsi_group_title
    result_title = body_load['result']['itsi_group_title']
    pd_body['search_name'] = result_title

    #Update link to event (requires import re)
    #FROM Core Splunk https://<server>/app/SA-ITOA/@go?sid=<sid_here>
    #TO ITSI https://<server>/app/itsi/itsi_event_management?earliest=-24h&episodeid=<itsi_group_id>&tabid=impact
    results_link = body_load['results_link']
    result_itsi_group_id = body_load['result']['itsi_group_id']
    new_link = 'itsi/itsi_event_management?earliest=-24h&episodeid=' + result_itsi_group_id + '&tabid=impact'
    updated_results_link = re.sub(r'SA-ITOA.*', new_link, results_link)
    pd_body['results_link'] = updated_results_link

    #Update other fields
    pd_body['configuration'] = body_load['configuration']    #configuration includes token, integration_url, integration_url_override
    pd_body['app'] = body_load['app']

    pd_body['result'] = {}
    pd_body['result']['correlation_search_name'] = body_load['result']['search_name']
    pd_body['result']['_raw'] = body_load['result']['orig_raw']
    pd_body['result']['itsi_group_description'] = body_load['result']['itsi_group_description']
    pd_body['result']['_time'] = body_load['result']['orig_time']

    #Map severity
    try:
        results_severity = int(body_load['result']['severity'])    #ITSI severity is 1-6, cast to integer before modifying
        updated_severity = modify_severity(results_severity)
        pd_body['result']['log_level'] = updated_severity
    except:
        logger.error("Error setting severity mapping for PagerDuty")
        pd_body['result']['log_level'] = 'CRITICAL'

    #Include optional fields if they exist
    if 'actual_time' in body_load['result']:
        pd_body['result']['actual_time'] = body_load['result']['actual_time']

    if 'service_name' in body_load['result']:
        pd_body['result']['service_name'] = ''
        pd_body['result']['service_name'] = body_load['result']['service_name']

    if 'drilldown_title' in body_load['result']:
        drilldown_title = body_load['result']['drilldown_title']
        pd_body['result'][drilldown_title] = ''
        if 'drilldown_uri' in body_load['result']:
            pd_body['result'][drilldown_title] = body_load['result']['drilldown_uri']
    elif 'drilldown_uri' in body_load['result']:
        pd_body['result']['drilldown_uri'] = body_load['result']['drilldown_uri']

    return pd_body

def modify_severity(itsi_severity):
    #Function to map ITSI severity (integer) to PagerDuty severity.  Low and High urgency are the only options used in our environment.
    #Valid PagerDuty values: ERROR, WARN, CRITICAL, FATAL
    sev_map={
        1:'WARN',
        2:'WARN',
        3:'WARN',
        4:'WARN',
        5:'CRITICAL',
        6:'CRITICAL'
    }
    return sev_map.get(itsi_severity,'CRITICAL')


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--execute":
        payloadStr = sys.stdin.read()
        payload = json.loads(payloadStr)
        success = send_notification(payload)
        if not success:
            logger.error("Failed trying to send incident alert")
            sys.exit(2)
        else:
            logger.info("Incident alert notification successfully sent")
    else:
        logger.error("FATAL Unsupported execution mode (expected --execute flag)")
        sys.exit(1)