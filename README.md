# Splunk ITSI PagerDuty Alerts
Splunk ITSI -> PagerDuty integration

This is based on the original source code from Martin Stone at https://github.com/martindstone/pagerduty-itsi.

This is a Notable Event Action that triggers a PagerDuty incident.  The following are updates from Martin Stone's original project:
1. PagerDuty now has a standard Splunk integration.  The same integration can be used for Core Splunk and ITSI, but field mappings require a bit of changing from ITSI.
2. PagerDuty now includes incidents and alerts.  By default, incidents are grouped and an incident number is not generated.  If alerts are disabled for a service, an incident number is still not a unique value so retrieving an incident number from PagerDuty has been commented out in the code.
3. Changed notable event action verbiage from "Trigger PagerDuty Incident" to "PagerDuty Incident Integration" to align with Splunk's Remedy Add-On verbiage
4. Updated logging to follow ITSI standard logging
5. HTTP call is routed through proxy in our environment, if not needed remove the proxy routing from the python script

## Instructions for use:

1. Create a Splunk Integration in PagerDuty as the default

3. Copy pagerduty_itsi.py to SPLUNK_HOME/etc/apps/SA-ITOA/bin

4. Copy pagerduty_itsi.html to SPLUNK_HOME/etc/apps/SA-ITOA/default/data/ui/alerts

5. Edit SPLUNK_HOME/etc/apps/SA-ITOA/local/alert_actions.conf and add the following text at the bottom:

	```
	[pagerduty_itsi]
	is_custom = 1
	param.integration_url = <your integration URL from Step 1>
	param.token = <your API token from Step 2>
	label = Trigger PagerDuty Incident
	description = Trigger an incident in PagerDuty
	payload_format = json
	```

6. Edit SPLUNK_HOME/etc/apps/SA-ITOA/local/notable_event_actions.conf and add the following text at the bottom:

	```
	[pagerduty_itsi]
	disabled = 0
	execute_once_per_group = 0
	```

7. Restart Splunk: SPLUNK_HOME/bin/splunk restart

You should now see a new item called "PagerDuty Incident Integration" in the Actions menu in Notable Events.