#!/usr/bin/env python
# William Zhang
from junos import Junos_Context
from jnpr.junos import Device
from jnpr.junos.resources.interface import InterfaceTable
import jcs


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
    #print(output)
    '''
    for key in tab.keys():
        #output = get_interface_ip_addresses(dev, key, primary_only=True)
        print(key)
        print(key.unit_name)
        #print(output)
    '''
    dev.close()
    return


if __name__ == '__main__':
    main()
