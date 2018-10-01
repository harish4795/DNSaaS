#startup application code for VPC-DNS service
#assumes customer has a VPC set up
#from ansible import callbacks,playbook

import os
import subprocess
import configparser
import json
import random
from collections import OrderedDict

create_container_ansible = 'proj/ansible/createContainers.yaml'

def run_playbook(net_loc, args_pass):
        str="sudo ansible-playbook "+net_loc + " -e " + args_pass
        os.system(str)
        return 0

def create_container(no_of_dns):
        for i in range(1,no_of_dns+1):
                os.system("sudo ansible-playbook "+create_container_ansible+" -e container_names=dns"+str(i))

def create_veth(bridge_list):
        for i in range(1,no_of_dns+1):
                os.system("sudo ip link add dns"+str(i)+bridge_list[i-1]+"0 type veth peer name dns"+str(i)+bridge_list[i-1]+"1")
                pid = subprocess.check_output(['sudo','docker','inspect','-f',"'{{.State.Pid}}'",'dns'+str(i)]).strip()
                os.system("sudo ip link set dev dns"+str(i)+bridge_list[i-1]+"0 netns "+pid+" name dns"+str(i)+bridge_list[i-1]+"0")
                os.system("sudo ovs-vsctl add-port "+bridge_list[i-1]+" dns"+str(i)+bridge_list[i-1]+"1")
                veth_list.append("dns"+str(i)+bridge_list[i-1]+"0")

def assign_ip(veth_list):
        config = configparser.ConfigParser()
        config.read('client.ini')

        no_of_veth = len(veth_list)
        for i in range(1,no_of_veth+1):
                host_address=[]
                net = 'NET'+str(i)
                ip_addresses = json.loads(config[net]['ip_addresses'])
                no_of_ip = len(ip_addresses)
                subnet_mask = int(dns_subnets[i-1].split('/')[1])
                network_address = dns_subnets[i-1].split('.')[0:(subnet_mask/8)]
                network_address = '.'.join(network_address)
                for j in range(no_of_ip):
                        host_address.append(int(ip_addresses[j].split('.')[-1].split('/')[0]))
                flag=0
                while(flag!=1):
                        dns_host_ip = random.randint(1,255)
                        if(dns_host_ip not in host_address):
                                flag=1
                dns_ip = network_address+'.'+str(dns_host_ip)+'/'+str(subnet_mask)
                zone_address.append(str(network_address)+'.'+str(dns_host_ip))
                os.system("sudo docker exec --privileged dns"+str(i)+" ip link set dev dns"+str(i)+bridge_list[i-1]+"0 up")
                os.system("sudo ip link set dev dns"+str(i)+bridge_list[i-1]+"1 up")
                os.system("sudo docker exec --privileged dns"+str(i)+" ip addr add "+dns_ip+" dev dns"+str(i)+bridge_list[i-1]+"0")

def extract_net_servers(index):
        config = configparser.ConfigParser()
        config.read('client.ini')
        net = 'NET'+str(index)
        dept_names = json.loads(config[net]['dept'])
        no_of_dept = len(dept_names)
        net_server=[]
        for dept in dept_names:
                dept_ip_add = json.loads(config[net]['www.'+ str(dept)])
                host_and_ip_dict=OrderedDict()
                for ip in dept_ip_add:
                        host_and_ip_dict['hostname']='www.'+ str(dept)
                        host_and_ip_dict['ip']= str(ip)
                        net_server.append(host_and_ip_dict)
                        host_and_ip_dict = OrderedDict()
        return net_server


if __name__ == '__main__':
        print("Welcome to our Cloud DNS service. We help you provide DNS service to your Private Cloud setup. Enjoy the Ride!!")
        print("Enter the number of subnets in your private cloud")
        no_subnets=input()

        print("enter subnet/s in which to create DNS seperating each subnet by comma Ex:192.168.10.0/24,192.168.20.0/24")
        dns_subnets = raw_input().split(',')
        no_of_dns = len(dns_subnets)
        zone = raw_input('Enter Zone Name\r\n')
        zone += "."
        print("zone name: " + zone)
        zone_address =[]
        bridge_list=[]
        zone_names =[]
        veth_list=[]
        name_servers=[]
        allow_query_from = ""
        args_pass = "-e "
        for subnet in dns_subnets:
                if '/' not in subnet:
                        print('Error: enter subnets with subnet masks eg: /16, /24')
                        exit()
                s=list(subnet)

                if s[len(s)-4]!='0':
                        print('Error:Enter a network address eg: 192.168.10.0/24')
                        exit()
                print('Enter the bridge name to which your subnet is connected to eg:l2,l2br')
                bridge_list.append(raw_input())
                allow_query_from +=subnet+"; "

        allow_query_from = allow_query_from[:-1]
        print("\r\nAllow query parameter to ansible" + str(allow_query_from))

        for i in range(0,no_of_dns):
                name_servers.append("dns" + str(i+1) + "." + zone + ".")
                zone_names.append(str(zone) + "-net" + str(i+1) + ".zone")
        print("\r\n\r\nForward zone names: "+ str(zone_names) + "\r\n")

        create_container(no_of_dns)
        create_veth(bridge_list)
        assign_ip(veth_list)

        netserver_list=[]
        for i in range(0,no_of_dns):
                net_server_list = extract_net_servers(i+1)
                print("Net server list:" + str(i+1) + str(net_server_list) + "\r\n")
                netserver_list.append(str(net_server_list))


        networks_list = []
        network_dict=OrderedDict()
        for i in range(0,no_of_dns):
                network_dict['net'] = "net" + str(i+1)
                network_dict['ip'] = str(dns_subnets[i])
                network_dict['view'] = "net" + str(i+1) + "-view"
                network_dict['forward_zone'] = str(zone_names[i])
                subnet_mask = int(dns_subnets[i].split('/')[1])
                revzone ='.'.join(dns_subnets[i].split('/')[0].split('.')[::-1][(4-subnet_mask/8):])
                network_dict['rev_zone'] = revzone
                print("\r\n\r\n Networks Dict: " + str(network_dict) + "\r\n\r\n")
                networks_list.append(network_dict)

        print("\r\n\r\n\r\n Networks list: " + str(networks_list))

        args_pass = "\'{'zone': " + str(zone) + ", 'zone_names': " + str(zone_names) + ", 'zone_address': " + str(zone_address) + ", 'allow_query': " + str(allow_query_from) + ", 'name_server': " + str(name_servers) + ", 'netserver': " + str(netserver_list) + ", networks': " + str(networks_list)

        run_playbook('main.yaml', args_pass)
        #status,output = commands.getstatusoutput('sudo docker ps')
        #l3_net = 'proj/ansible/.yaml'
        #status=run_playbook(l3_net)
        #if status==0:

