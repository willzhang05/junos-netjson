#!/usr/bin/env python
# William Zhang
from junos import Junos_Context
from jnpr.junos import Device
from lxml import etree
import jcs
import httplib
import urllib
import uuid


def get_interface_ip_addresses(dev, ifl, primary_only=False):
    output = dev.rpc.get_interface_information(interface_name=ifl)
    find = etree.XPath("//logical-interface/address-family")
    matches = find(output)
    filtered = None
    for m in matches:
        type_find = etree.XPath("//address-family-name[contains(.,'inet')]")
        type_res = type_find(m)
        if len(type_res) != 0:
            filtered = m
            break
    addr = []
    addr_find = etree.XPath("interface-address")
    if filtered is not None:
        matches = addr_find(filtered)
        for m in matches:
            if primary_only:
                primary_find = etree.XPath("ifa-flags/ifaf-current-primary")
                primary_res = primary_find(m)
                if len(primary_res) == 0:
                    continue
            ifa_find = etree.XPath("ifa-local")
            ifa_res = ifa_find(m)
            if len(ifa_res) != 0:
                addr.append(ifa_res[0].text.strip())
    return addr


def get_node_info(dev):
    ifaces = []
    addresses = []
    output = dev.rpc.get_lldp_local_info()
    mgmt_if_find = etree.XPath(
        "//lldp-local-management-address-interface-name")
    mgmt_if = mgmt_if_find(output)
    mgmt_if_name = ""
    if len(mgmt_if) != 0:
        mgmt_if_name = mgmt_if[0].text.strip()

    if_find = etree.XPath("//lldp-local-interface-name")
    lldp_if = if_find(output)
    if len(lldp_if) != 0:
        for iface in lldp_if:
            iface_name = iface.text.strip()
            if iface_name != mgmt_if_name:
                ifaces.append(iface.text.strip())

    for i in ifaces:
        addr = get_interface_ip_addresses(dev, i, primary_only=True)
        addresses += addr

    mgmt_addr_find = etree.XPath("//lldp-local-management-address-address")
    mgmt_addr = mgmt_addr_find(output)[0].text.strip()

    hostname_find = etree.XPath("//lldp-local-system-name")
    hostname = hostname_find(output)[0].text.strip()

    id_find = etree.XPath("//lldp-local-chassis-id")
    chassis_id = id_find(output)[0].text
    host_id = str(hostname + ''.join(chassis_id.split(":")))

    hex_host_id = bytes(host_id.ljust(16)[:16])
    host_id = uuid.UUID(bytes=hex_host_id)

    data = {}
    data['id'] = chassis_id
    data['label'] = hostname + " - " + mgmt_addr
    data['properties'] = {}
    data['properties']['hostname'] = hostname
    data['properties']['address'] = mgmt_addr
    data['local_addresses'] = addresses
    return (ifaces, data)


def get_link_info(dev, node_data):
    output = dev.rpc.get_lldp_neighbors_information()
    neighbor_find = etree.XPath("//lldp-remote-chassis-id")
    neighbors = neighbor_find(output)

    data = []
    for neighbor in neighbors:
        entry = {}
        entry['source'] = node_data['id']
        entry['target'] = neighbor.text.strip()
        data.append(entry)

    return data


def main():
    dev = Device()
    dev.open()

    node_ifaces, node_data = get_node_info(dev)
    print(node_data)
    link_data = get_link_info(dev, node_data)
    print(link_data)
    dev.close()
    return


if __name__ == '__main__':
    main()
