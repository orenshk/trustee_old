import re
import os
import sys
import time
import argparse
import subprocess

import boto3
from botocore.exceptions import ClientError

# boto clients shared by everyone
ec2 = boto3.client('ec2')
route53 = boto3.client('route53')

def _get_hosted_zone_id_from(hosted_zone_name) -> str:
    response = route53.list_hosted_zones_by_name(DNSName=hosted_zone_name)
    if len(response['HostedZones']) == 0:
        raise RuntimeError(f'No record found for {hosted_zone_name}')

    return response['HostedZones'][0]['Id']

def _get_hostname_ip(hostname: str, hosted_zone_id: str) -> str:
    response = route53.list_resource_record_sets(HostedZoneId=hosted_zone_id, StartRecordName=hostname)
    if len(response['ResourceRecordSets']) == 0:
        raise RuntimeError(f'No record found for {hostname} in hosted zone with id {hosted_zone_id}')

    # list_resource_record_sets returns all sets with name >= StartRecordName. We just have to make sure the first one is what we're looking for. 
    resource_record_set = response['ResourceRecordSets'][0]
    # strip the training '.' from the address.
    if resource_record_set['Name'][:-1] != hostname:
        raise RuntimeError(f'No record found for {hostname}, instead got {resource_record_set["Name"]}, are you sure you got the right hostname?')

    return resource_record_set['ResourceRecords'][0]['Value']

def _parse_args(args):
    parser = argparse.ArgumentParser('trust-ec2-host')
    instance_identifiers = parser.add_mutually_exclusive_group(required=True)
    instance_identifiers.add_argument('--ip', type=str, default=None, help='IP of AWS instance you want to verify.')
    instance_identifiers.add_argument('--dns-name', type=str, default=None, help='public dns of AWS instance you want to verify.')
    instance_identifiers.add_argument('--instance-id', type=str, default=None, help='ID of the AWS instance you want to verify.')
    instance_identifiers.add_argument('--hostname', type=str, default=None, help='fixed hostname for the machine you want to verify. Assumed to be of the form subdomain.aws-hosted-zone-string.')
    parser.add_argument('-n', '--num-tries', default=5, type=int)
    parser.add_argument('-s', '--sleep-time', default=60, type=int)

    return parser.parse_args(args)



def main(args: argparse.Namespace=None):
    args = _parse_args(args)
    ec2 = boto3.client('ec2')
    # we'll try to record as many aliases for the machine as we can, aws public dns, ip, and if available some fixed domain name.
    identifiers = []
    if args.instance_id:
        filters = [{'Name': 'instance-id', 'Values': [args.instance_id]}]
    elif args.ip:
        filters = [{'Name': 'ip-address', 'Values': [args.ip]}]
    elif args.dns_name:
        filters = [{'Name': 'dns-name', 'Values': [args.dns_name]}]
    else:
        # get record from route53
        # we're assuming here that the domain has the form subdomain.aws-hosted-zone-with-one-or.more-dots.domain
        _, hosted_zone_name = args.hostname.split('.', 1)
        hosted_zone_id = _get_hosted_zone_id_from(hosted_zone_name)
        filters = [{'Name': 'ip-address', 'Values': [_get_hostname_ip(args.hostname, hosted_zone_id)]}]
        identifiers.append(args.hostname)
    
    response = ec2.describe_instances(Filters=filters)        
    if len(response['Reservations']) == 0:
        raise RuntimeError(f"Couldn't find instance with ip/dns: {filters[0]['Values'][0]}")

    instance_info = response['Reservations'][0]['Instances'][0]
    instance_id = instance_info['InstanceId']
    identifiers.extend([instance_info['PublicIpAddress'], instance_info['PublicDnsName']])

    max_num_tries = args.num_tries
    sleep_time = args.sleep_time

    key_re = re.compile('\r\n(ecdsa-sha2-nistp256 .*) ')

    console_output = ''
    num_tries = 0
    # Might take a while for the console to appear, and we should be careful about the instance id as well.
    # we'll try some maximum number of times before giving up.
    while not console_output and num_tries < max_num_tries:
        try:
            response = ec2.get_console_output(InstanceId=instance_id)
            console_output = response['Output']
            if not console_output:
                raise ValueError('console output not ready')
        except (ClientError, ValueError):
            print(f'Console output is not ready, sleeping for {sleep_time} seconds'.format(sleep_time))
            time.sleep(sleep_time)

        num_tries += 1

    match = key_re.search(console_output) 

    if not match:
        raise RuntimeError('Cannot find key in console output. Is this instance too old?')

    
    for identifier in identifiers:
        subprocess.check_call(['ssh-keygen', '-R', identifier])
    
    with open(os.path.join(os.path.expanduser('~'), '.ssh', 'known_hosts'), 'a') as known_hosts:
        new_host = f'{",".join(identifiers)} {match.group(1)}\n'
        known_hosts.write(new_host)
    

if __name__ == '__main__':
    main()
