#!/usr/bin/env python
# William Zhang
from junos import Junos_Context
from jnpr.junos import Device
from lxml import etree
import jcs
import httplib, urllib
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
    if filtered:
        matches = addr_find(filtered)
        for m in matches:
            if primary_only:
                primary_find = etree.XPath("ifa-flags/ifaf-current-primary")
                primary_res = primary_find(m)
                if len(primary_res) == 0:
                    continue
            dest_find = etree.XPath("ifa-destination")
            dest_res = dest_find(m)

            ifa_find = etree.XPath("ifa-local")
            ifa_res = ifa_find(m)
            if len(ifa_res) != 0:
                if len(dest_res) == 0:
                    addr.append(ifa_res[0].text.strip() + "/32")
                else:
                    addr.append(dest_res[0].text.strip())
    return addr


def main():
    dev = Device()
    dev.open()
    output = dev.rpc.get_interface_information()
    find = etree.XPath("//logical-interface/name")
    matches = find(output)
    addresses = []
    for m in matches:
        name = m.text.strip()
        addr = get_interface_ip_addresses(dev, name, primary_only=True)
        addresses += addr
        #print(output)
    output = dev.rpc.get_system_information()
    hostname_find = etree.XPath("//host-name")
    hostname = hostname_find(output)[0].text
    print(hostname)

    hex_hostname = bytes(hostname.ljust(16))
    print(hex_hostname)
    print(type(hex_hostname))
    host_id = uuid.UUID(bytes=hex_hostname)

    data = {}
    data['id'] = str(host_id)
    data['label'] = hostname
    data['local_addresses'] = set(addresses)
    print(data)
    dev.close()
    return


if __name__ == '__main__':
    main()
