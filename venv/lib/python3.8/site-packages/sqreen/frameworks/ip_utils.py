# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Utils functions to retrieve the client user ip
"""

from ..utils import ip_address


def get_real_user_ip(remote_addr, *ips):
    """ Try to compute the real user ip from various headers
    """
    private_ip = None
    for list_ips in ips:
        for ip in list_ips.split(","):
            ip = ip.strip()
            if not ip:
                # Dummy IP address, skip it.
                continue
            try:
                # Azure append the port to IPv4 in XFF headers. We need to strip it
                if '.' in ip and ':' in ip:
                    ip = ip.split(':')[0]

                ip = ip_address(ip)
            except ValueError:
                continue
            if ip.is_global:
                return ip
            elif private_ip is None and not ip.is_loopback and ip.is_private:
                private_ip = ip
    # If no global IP was found so far.
    try:
        remote_ip = ip_address(remote_addr)
    except ValueError:
        return private_ip  # May be None.
    if private_ip is None or remote_ip.is_global:
        return remote_ip
    else:
        return private_ip
