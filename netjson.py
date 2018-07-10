#!/usr/bin/env python
# William Zhang
from junos import Junos_Context
from jnpr.junos import Device
from lxml import etree
import argparse
import jcs
import httplib
import urllib
import urlparse
import uuid
import json
import httplib


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
    host_id = str(hostname + "".join(chassis_id.split(":")))

    hex_host_id = bytes(host_id.ljust(16)[:16])
    host_id = uuid.UUID(bytes=hex_host_id)

    data = {}

    data["id"] = chassis_id
    data["label"] = hostname + " - " + mgmt_addr
    data["properties"] = {}
    data["properties"]["hostname"] = hostname
    data["properties"]["address"] = mgmt_addr
    #data["local_addresses"] = addresses
    return (ifaces, data)


def get_link_info(dev, node_data):
    output = dev.rpc.get_lldp_neighbors_information()
    neighbor_find = etree.XPath("//lldp-remote-chassis-id")
    neighbors = neighbor_find(output)

    data = []
    for neighbor in neighbors:
        entry = {}
        entry["source"] = node_data["id"]
        entry["target"] = neighbor.text.strip()
        entry["cost"] = 1
        data.append(entry)

    return data


def get_neighbor_info(dev, iface):
    output = dev.rpc.get_lldp_interface_neighbors(interface_device=iface)
    neighbor_find = etree.XPath("//lldp-neighbor-information")
    neighbors = neighbor_find(output)
    data = []
    for neighbor in neighbors:
        entry = {}
        chassis_id_find = etree.XPath("//lldp-remote-chassis-id")
        chassis_id = chassis_id_find(neighbor)[0].text

        hostname_find = etree.XPath("//lldp-remote-system-name")
        hostname = hostname_find(neighbor)[0].text

        mgmt_addr_find = etree.XPath("//lldp-remote-management-address")
        mgmt_addr = mgmt_addr_find(neighbor)
        address = mgmt_addr[0].text.strip() if len(
            mgmt_addr) != 0 else 'unknown'
        entry["id"] = chassis_id
        entry["label"] = hostname + " - " + address
        entry["properties"] = {}
        entry["properties"]["hostname"] = hostname
        entry["properties"]["address"] = address
        #entry["local_addresses"] = addresses
        data.append(entry)

    return data


def main():
    arguments = {"send": "API POST Endpoint to send NetJSON to.",
                 "recv": "API GET Endpoint to receive NetJSON from."}
    parser = argparse.ArgumentParser(description="NetJSON op script")
    for key in arguments:
        parser.add_argument(('-' + key), required=False, help=arguments[key])
    args = parser.parse_args()
    graph = {}
    if args.recv is not None:
        url = urlparse.urlparse(args.recv)
        conn = httplib.HTTPSConnection(url.netloc)
        params = urlparse.parse_qs(url.query)
        conn_path = url.path + "?format=json"
        conn.request("GET", conn_path)
        response = conn.getresponse()
        if response.status == 200:
            graph = json.loads(response.read())
            print(graph)
            print()
        else:
            print("Invalid recv URL.")
            return 1

    dev = Device()
    dev.open()

    node_if, node_data = get_node_info(dev)
    link_data = get_link_info(dev, node_data)
    neighbor_data = []

    print(node_if)
    neighbor_ids = set()
    for iface in node_if:
        neighbors = get_neighbor_info(dev, iface)
        for neighbor in neighbors:
            if neighbor['id'] not in neighbor_ids:
                neighbor_ids.add(neighbor['id'])
                neighbor_data.append(neighbor)

    dev.close()

    graph["type"] = "NetworkGraph"
    graph["protocol"] = "static"
    graph["version"] = "1.0"
    graph["metric"] = "1.0"

    if len(graph["nodes"]) != 0:
        for node in graph["nodes"]:
            if node["id"] == node_data["id"]:
                node["label"] = node_data["label"]
                node["local_addresses"] = node_data["local_addresses"]
                node["properties"] = node_data["properties"]
    else:
        graph["nodes"].append(node_data)
        graph["nodes"] += neighbor_data

    links = []

    if len(graph["links"]) != 0:
        for existing_link in graph["links"]:
            for local_link in link_data:
                exists_locally = False
                if existing_link["source"] == local_link["source"] and existing_link["target"] == local_link["target"] \
                        or existing_link["source"] == local_link["target"] and existing_link["target"] == local_link["source"]:
                    exists_locally = True
                else:
                    links.append(local_link)
                if existing_link["source"] == node_data[
                        "id"] or existing_link["target"] == node_data["id"]:
                    if exists_locally:
                        links.append(local_link)

    else:
        links += link_data

    graph["links"] = links

    print(json.dumps(graph))

    if args.send is not None:
        print(args.send)
        url = urlparse.urlparse(args.send)
        conn = httplib.HTTPSConnection(url.netloc)
        params = urlparse.parse_qs(url.query)
        conn_path = url.path + "?key=" + params['key'][0]
        print(conn_path)
        params = json.dumps(graph)
        conn.request("POST", conn_path, params)
        response = conn.getresponse()
        print(response.status, response.reason)
    return


if __name__ == "__main__":
    main()
