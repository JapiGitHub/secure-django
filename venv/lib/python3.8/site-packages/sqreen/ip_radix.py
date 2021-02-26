# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#

"""Radix tree implementation optimized to process IPs numerically"""

import struct
import sys
from logging import getLogger

from sqreen.utils import ip_address, ip_network

from ._vendors.ipaddress import (
    IPv4Address,
    IPv4Network,
    IPv6Address,
    IPv6Network,
)

IS_PYTHON_2 = sys.version_info.major == 2
LOGGER = getLogger(__name__)


class Node(object):
    """Node of the tree"""

    def __init__(self, bit_width):
        """Initialize the node to its default value"""
        self.value = 0
        self.depth = 0
        self.length = 0
        self.bit_width = bit_width
        self.is_network = False
        self.node0 = None
        self.node1 = None
        self.payload = None

    def set_root(self, ip, is_network):
        """Configure a node as the root node of the radix tree"""
        if ip.version == 4:
            self.bit_width = 32
        else:
            self.bit_width = 128

        self.value = Radix.get_value(ip, is_network)
        self.depth = 0
        self.is_network = is_network
        if is_network:
            self.length = ip.prefixlen
        else:
            self.length = self.bit_width

    def is_empty_root(self):
        """Return whether this node is the root node and is empty (which is different from a single root node containing a all-zero IP"""
        return self.depth == 0 and self.length == 0 and self.node0 is None

    def set_value(self, ip_value, length_to_insert, is_network):
        """Small method setting the value of a node, only picking a few bits from an overall value"""
        self.value = ip_value
        self.value &= (1 << length_to_insert) - 1

        self.depth = self.bit_width - length_to_insert
        self.length = length_to_insert
        self.is_network = is_network

    def get_polarity(self):
        """Return the highest relevant bit (according to the depth and length of the node) is"""
        return (self.value >> (self.bit_width - 1 - self.depth)) & 1

    def clamp_value(self):
        """Constraint the value of a node to the relevant range, according to its depth and length.
        Make shenanigans with the node position easier to pull off, especially considering the bit magic involved
        """
        upper_clamp = self.bit_width - self.depth
        lower_clamp = upper_clamp - self.length

        self.value &= ((1 << upper_clamp) - 1)
        self.value &= ~((1 << lower_clamp) - 1)

    def restrict_length(self, new_length, other_new_child):
        """Reduce the length of the node, turning what is left in a child of this node"""
        length_to_remove = self.length - new_length
        if new_length <= 0 or length_to_remove <= 0:
            LOGGER.error("Radix Tree internal inconsistency: restrict length called with new_length %d with length_to_remove %d", new_length, length_to_remove)
            return False

        if self.is_network:
            network_offset = self.bit_width - self.depth - self.length
        else:
            network_offset = 0

        # Create a new child with the section we have to remove, assuming we even want to keep it
        new_child = Node(self.bit_width)
        new_child.value = self.value
        new_child.payload = self.payload
        new_child.is_network = self.is_network
        new_child.length = length_to_remove + network_offset
        new_child.depth = self.depth + new_length
        new_child.clamp_value()
        new_child.length -= network_offset

        if self.node0 is not None or self.node1 is not None:
            if self.is_network:
                LOGGER.error("Radix Tree internal inconsistency: IP ranges are not supposed to have children! %s", self)
                return False

            new_child.node0 = self.node0
            new_child.node1 = self.node1

        if new_child.get_polarity() == other_new_child.get_polarity():
            LOGGER.warning("Radix Tree internal inconsistency: we likely made a mistake computing the length to remove from a node")
            return False

        # We now need to determine the polarity of new_child to know to which node[0-1] we need to set it to
        if new_child.get_polarity():
            self.node0 = other_new_child
            self.node1 = new_child
        else:
            self.node0 = new_child
            self.node1 = other_new_child

        # Remove a section at our end
        self.length = new_length
        self.payload = None
        self.clamp_value()
        self.is_network = False
        return True

    def remove_child_with_polarity(self, polarity):
        """Remove one of our child and merge the orphan with us"""
        if self.node0 is None or self.node1 is None:
            LOGGER.warning("Radix Tree internal inconsistency: trying to remove a child from a node without children")
            return

        # We're removing node1, so we have to merge with node0
        if polarity:
            worthy_child = self.node0
        else:
            worthy_child = self.node1

        self.length += worthy_child.length
        self.value |= worthy_child.value
        self.is_network = worthy_child.is_network
        self.payload = worthy_child.payload
        self.node0 = worthy_child.node0
        self.node1 = worthy_child.node1

    def all_payloads(self):
        if self.payload:
            yield self.payload

        if self.node0:
            for p in self.node0.all_payloads():
                yield p

        if self.node1:
            for p in self.node1.all_payloads():
                yield p

    def __str__(self, parent_value=0):
        """Recursively generate the string representation of the node and its children,
           by passing the values of the higher bits"""

        if self.is_empty_root():
            return ""

        parent_value |= self.value

        if self.node0 is not None:
            output = self.node0.__str__(parent_value) + ", " + self.node1.__str__(parent_value)
        else:
            if self.bit_width == 32:
                output = str(IPv4Address(parent_value))
            else:
                output = str(IPv6Address(parent_value))

            if self.is_network:
                mask_width = self.depth + self.length
                output += "/" + str(mask_width)

        return output


class Radix(object):
    """Main data structure of the Radix tree. Contains two trees: one for IPv4, one for IPv6"""
    def __init__(self, ip, is_network=False):
        """Initialize the two tries"""
        self.root4 = Node(32)
        self.root6 = Node(128)

        ip = self.enforce_ip(ip, is_network)
        if ip is not None:
            if ip.version == 4:
                self.root4.set_root(ip, is_network)
            else:
                self.root6.set_root(ip, is_network)

            self.empty = False
        else:
            self.empty = True

    @staticmethod
    def create_ip(ip, is_network):
        """Convert, if necessary, the input IP into the appropriate object"""
        if ip is None:
            return None

        if is_network:
            if isinstance(ip, IPv4Network) or isinstance(ip, IPv6Network):
                return ip
            if IS_PYTHON_2 and isinstance(ip, bytes):
                ip = ip.decode("utf-8")
            try:
                return ip_network(ip, False)
            except ValueError:
                return None

        else:
            if isinstance(ip, IPv4Address) or isinstance(ip, IPv6Address):
                return ip
            if IS_PYTHON_2 and isinstance(ip, bytes):
                ip = ip.decode("utf-8")
            try:
                return ip_address(ip)
            except ValueError:
                return None

    @classmethod
    def enforce_ip(cls, ip, is_network):
        """Wrap around create_ip and turn IPv4 addresses mapped in IPv6 back into IPv4"""
        ip_object = cls.create_ip(ip, is_network)

        # IPv6 addresses may actually be hidden IPv4 addresses. We want to detect them and move them to the proper tree
        if ip_object is None or ip_object.version != 6:
            return ip_object

        ip_value = cls.get_value(ip_object, is_network)
        ip_value_without_ipv4 = ip_value >> 32
        # The two approaches are ::0000:IPv4 (RFC4291 @ 2.5.5.1, deprecated) and ::ffff::IPv4 (RFC4291 @ 2.5.5.2)
        if ip_value_without_ipv4 == 0x0000 or ip_value_without_ipv4 == 0xffff:
            # Clear the bits higher of the numerical value, then create a new object (which will be IPv4 as the numerical value is low enough)
            ip_value &= 0xffffffff
            if not is_network:
                return IPv4Address(ip_value)

            # If this is a network, we have to check if the subnet is small enough
            if ip_object.prefixlen >= 96:
                return IPv4Network(ip_value)

        return ip_object

    def exist(self, ip, is_network=False):
        """Crawl the appropriate tree in order to check whether the IP represented by the object exist in the tree"""
        if self.empty:
            return None

        target_value = self.get_value(ip, is_network)
        if ip.version == 4:
            cur_node = self.root4
        else:
            cur_node = self.root6

        # Is the tree empty?
        if cur_node.node0 is None and cur_node.node1 is None and cur_node.length == 0:
            return None

        bit_width = cur_node.bit_width
        search_length_left = bit_width

        # The following algorithm is optimized to minimize the number of branches
        while True:

            # We check if the cur_node and the target share the same value.
            # This will however compare the whole address, instead of only the relevant section
            combined_value = target_value ^ cur_node.value

            # Mark the bits we just compared as done
            search_length_left -= cur_node.length

            # This will remove any irrelevant low bits from the compare result
            combined_value >>= search_length_left

            # The IP doesn't match the current node: the match fail
            values_match = combined_value == 0

            # We fully checked the IP. This would mean that assuming the values matched, the full IP match
            # If this node is a network we blocked, there is no need to go any further
            checked_full_ip = search_length_left == 0 or cur_node.is_network

            if not values_match or checked_full_ip:
                # If we're checking a network, the node we're matching to need to also be one
                if is_network:
                    values_match &= cur_node.is_network and (cur_node.depth + cur_node.length <= ip.prefixlen)

                if values_match:
                    return self.string_for_match(ip, cur_node, is_network)

                return None

            # This simply create a mask, removing any irrelevant bit
            target_value &= (1 << search_length_left) - 1

            # We pick the most significant bit
            highest_bit = target_value >> (search_length_left - 1)

            if highest_bit == 0:
                cur_node = cur_node.node0
            else:
                cur_node = cur_node.node1

    def match(self, ip, is_network=False):
        """Call .exist to check if an IP/network exist in the tree, but is more liberal in the input it will accept"""
        ip = self.enforce_ip(ip, is_network)
        if ip is None:
            return None

        return self.exist(ip, is_network)

    def insert(self, ip, is_network=False, payload=None):
        """Insert an IP/network in the tree"""
        ip = self.enforce_ip(ip, is_network)
        if ip is None:
            return False

        if ip.version == 4:
            cur_root = self.root4
        else:
            cur_root = self.root6

        cur_node = cur_root

        if self.empty or cur_root.is_empty_root():
            self.empty = False
            cur_node.set_root(ip, is_network)
            cur_node.payload = payload
            return True

        target_value = self.get_value(ip, is_network)
        search_length_left = cur_node.bit_width

        if self.exist(ip, is_network) is not None:
            return False

        # The following algorithm is based on `exist`, although duplicated in order to avoid adding anything to the hot path
        while True:

            combined_value = target_value ^ cur_node.value
            node_offset = search_length_left - cur_node.length
            combined_value >>= node_offset

            hit_end_network_mask = is_network and (cur_node.length + cur_node.depth >= ip.prefixlen)

            # Have we found the divergence point?
            if combined_value != 0 or hit_end_network_mask:

                # If a network, we remove the bits within the network mask
                if hit_end_network_mask:
                    network_mask_bits = (cur_node.length + cur_node.depth) - ip.prefixlen
                    node_offset += network_mask_bits
                    combined_value >>= network_mask_bits
                else:
                    network_mask_bits = 0

                # We compute the number of mismatched bits by progressively shifting the compare
                number_of_mismatched_bits = 0
                while (combined_value >> number_of_mismatched_bits) != 0:
                    number_of_mismatched_bits += 1

                # If we're adding a network, and we match with something within our mask,
                # all we really have to do is the shorten the node to only contain the network IP, remove any node and turn into a network
                if is_network and number_of_mismatched_bits == 0:
                    # We need to restrict the node's length to prefixlen. We make sure that this is possible. Otherwise, we bail out
                    if ip.prefixlen < cur_node.depth:
                        LOGGER.warning("Radix Tree internal inconsistency: We went too deep in the tree before inserting %s, which isn't supposed to be possible.", ip)
                        return False

                    cur_node.length = ip.prefixlen - cur_node.depth
                    cur_node.clamp_value()
                    cur_node.node0 = None
                    cur_node.node1 = None
                    cur_node.is_network = True
                    cur_node.payload = payload

                else:
                    new_node = Node(cur_node.bit_width)
                    new_node.set_value(self.get_value(ip, is_network), number_of_mismatched_bits + node_offset, is_network)
                    new_node.payload = payload

                    # Networks ignore a part of their address, this need to be reflected in their length. No need to update the value as it's already to 0
                    if is_network:
                        new_node.length = ip.prefixlen - new_node.depth

                    is_node_root = cur_node.depth == 0 and cur_node.length == cur_root.length

                    # Do we need to split the root node? (the last condition can only be false is something is going really wrong with .depth)
                    if not is_node_root or search_length_left != cur_node.bit_width:
                        # Nope! Awesome!
                        return cur_node.restrict_length(cur_node.length - number_of_mismatched_bits - network_mask_bits, new_node)

                    new_root = Node(cur_node.bit_width)
                    new_root.set_value(cur_node.value, cur_node.bit_width, False)
                    new_root.length = new_node.depth
                    # We add the full value to the root node, and we then need to clamp it
                    new_root.clamp_value()

                    cur_node.depth = new_node.depth
                    cur_node.length -= new_node.depth
                    cur_node.clamp_value()

                    # We check the polarity of the new node
                    if new_node.get_polarity():
                        new_root.node0 = cur_node
                        new_root.node1 = new_node
                    else:
                        new_root.node0 = new_node
                        new_root.node1 = cur_node

                    if ip.version == 4:
                        self.root4 = new_root
                    else:
                        self.root6 = new_root

                return True

            search_length_left -= cur_node.length
            if search_length_left == 0:
                return False

            if cur_node.is_network:
                return False

            target_value &= (1 << search_length_left) - 1
            highest_bit = target_value >> (search_length_left - 1)

            if highest_bit == 0:
                cur_node = cur_node.node0
            else:
                cur_node = cur_node.node1

    def remove(self, ip, is_network=False):
        """Remove an IP/network from the tree"""

        ip = self.enforce_ip(ip, is_network)
        if ip is None:
            return False

        if self.exist(ip, is_network) is None:
            return True

        if ip.version == 4:
            cur_node = self.root4
        else:
            cur_node = self.root6

        # Only one node exist and so are we. This mean we need to dump the root node. Ugh...
        if cur_node.length == cur_node.bit_width or cur_node.is_network:

            # Removing a smaller network or an ip from a network is not allowed
            if (is_network and ip.prefixlen > cur_node.depth + cur_node.length)\
                    or (not is_network and cur_node.is_network):
                return False

            cur_node.length = 0
            cur_node.node0 = cur_node.node1 = cur_node.payload = None

            if ip.version == 4:
                other_node = self.root6
            else:
                other_node = self.root4

            if other_node.is_empty_root():
                self.empty = True

            return True

        target_value = self.get_value(ip, is_network)
        current_offset = cur_node.bit_width - 1

        while current_offset > 0:

            # The next node is down the node1 path
            next_polarity = (target_value >> (current_offset - cur_node.length)) & 1
            if next_polarity:
                next_node = cur_node.node1
            else:
                next_node = cur_node.node0

            # We advance the current_offset
            current_offset -= cur_node.length

            # We ran in a network. This is a bit of a weird case where some cases are not allowed
            if next_node.is_network:
                # This is a network, and we're trying to extract a single IP which isn't supported yet
                if not is_network:
                    return False

                # If the network we're trying to remove is a subnet of this network, this is again not supported
                if next_node.depth + next_node.length < ip.prefixlen:
                    return False

                # Network nodes can't have children, meaning that the next call will trigger
                if next_node.node0 is not None or next_node.node1 is not None:
                    LOGGER.warning("Radix Tree internal inconsistency: found a network node with children")
                    next_node.node0 = next_node.node1 = None

            # Is the next node hitting the bottom? If so, it doesn't have children and we found the need we wanted to delete
            if next_node.node0 is None:
                cur_node.remove_child_with_polarity(next_polarity)
                return True

            # We proceed
            cur_node = next_node

        return False

    def clear(self):
        """Clear the tree"""
        if not self.empty:
            self.empty = True
            self.root4 = Node(self.root4.bit_width)
            self.root6 = Node(self.root6.bit_width)

    def all_payloads(self):
        for p in self.root4.all_payloads():
            yield p

        for p in self.root6.all_payloads():
            yield p

    @staticmethod
    def get_value(ip, is_network):
        """Return an integer containing the numerical value of the bit representation of an IP"""
        if is_network:
            target_array = ip.network_address.packed
        else:
            target_array = ip.packed

        if ip.version == 4:
            if IS_PYTHON_2:
                return struct.unpack('>I', target_array)[0]

            return (target_array[0] << 24) | (target_array[1] << 16) | (target_array[2] << 8) | target_array[3]
        else:
            if IS_PYTHON_2:
                target_array = struct.unpack('>QQ', target_array)
                return target_array[0] << 64 | target_array[1]

            output = 0
            for ip_item in target_array:
                output <<= 8
                output |= ip_item

            return output

    @classmethod
    def string_for_match(cls, ip, node, ip_is_network):
        """Return the string corresponding to IP we matched from the tree (i.e. the rule we matched)"""
        # Do we have a specific payload to return?
        if node.payload is not None:
            return node.payload

        if not node.is_network:
            return str(ip)

        # Get the network IP's, based on the target's
        full_ip_value = cls.get_value(ip, ip_is_network)

        relevant_length = node.depth + node.length
        length_to_trim = node.bit_width - relevant_length
        if length_to_trim != 0:
            full_ip_value &= ~((1 << length_to_trim) - 1)

        # IPv4
        if node.bit_width == 32:
            return str(IPv4Address(full_ip_value)) + "/" + str(relevant_length)

        # IPv6
        return str(IPv6Address(full_ip_value)) + "/" + str(relevant_length)

    def __repr__(self):
        return "{}({!r})".format(self.__class__.__name__, str(self))

    def __str__(self):
        if self.empty:
            return ""

        radix_v4 = str(self.root4)
        radix_v6 = str(self.root6)

        if radix_v4 == "":
            return radix_v6

        elif radix_v6 == "":
            return radix_v4

        return radix_v4 + ", " + radix_v6
