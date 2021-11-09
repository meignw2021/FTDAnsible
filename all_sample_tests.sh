#!/bin/bash

samples=(
playbooks/ftd_configuration/access_policy.yml
playbooks/ftd_configuration/access_rule_with_applications.yml
playbooks/ftd_configuration/access_rule_with_intrusion_and_file_policies.yml
playbooks/ftd_configuration/access_rule_with_logging.yml
playbooks/ftd_configuration/access_rule_with_networks.yml
playbooks/ftd_configuration/access_rule_with_urls.yml
playbooks/ftd_configuration/access_rule_with_users.yml
playbooks/ftd_configuration/anyconnect_package_file.yml
playbooks/ftd_configuration/backup.yml
playbooks/ftd_configuration/data_dns_settings.yml
playbooks/ftd_configuration/deployment.yml
playbooks/ftd_configuration/dhcp_container.yml
playbooks/ftd_configuration/download_upload.yml
playbooks/ftd_configuration/ha_join.yml
playbooks/ftd_configuration/identity_policy.yml
playbooks/ftd_configuration/initial_provisioning.yml
playbooks/ftd_configuration/nat.yml
playbooks/ftd_configuration/network_object_with_host_vars.yml
playbooks/ftd_configuration/network_object.yml
playbooks/ftd_configuration/physical_interface.yml
playbooks/ftd_configuration/port_object.yml
playbooks/ftd_configuration/ra_vpn_license.yml
playbooks/ftd_configuration/ra_vpn.yml
playbooks/ftd_configuration/security_intelligence_url_policy.yml
playbooks/ftd_configuration/smart_license.yml
playbooks/ftd_configuration/ssl_policy.yml
playbooks/ftd_configuration/static_route_entry.yml
playbooks/ftd_configuration/sub_interface.yml    
)

for f in "$samples[@]"
do
 echo "Running playbook for $f"
 docker run -v $(pwd)/samples:/ftd-ansible/playbooks \
    -v $(pwd)/inventory/sample_hosts:/etc/ansible/hosts \
    ftd-ansible $f

done

