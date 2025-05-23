# Protected management frames tests
# Copyright (c) 2013-2024, Jouni Malinen <j@w1.fi>
#
# This software may be distributed under the terms of the BSD license.
# See README for more details.

from remotehost import remote_compatible
import binascii
import os
import time
import logging
logger = logging.getLogger()

import hwsim_utils
import hostapd
from utils import *
from wlantest import Wlantest
from wpasupplicant import WpaSupplicant
from test_eap_proto import rx_msg, tx_msg, proxy_msg

@remote_compatible
def test_ap_pmf_required(dev, apdev):
    """WPA2-PSK AP with PMF required"""
    ssid = "test-pmf-required"
    params = hostapd.wpa2_params(ssid=ssid, passphrase="12345678")
    params["wpa_key_mgmt"] = "WPA-PSK-SHA256"
    params["ieee80211w"] = "2"
    hapd = hostapd.add_ap(apdev[0], params)
    Wlantest.setup(hapd)
    wt = Wlantest()
    wt.flush()
    wt.add_passphrase("12345678")
    key_mgmt = hapd.get_config()['key_mgmt']
    if key_mgmt.split(' ')[0] != "WPA-PSK-SHA256":
        raise Exception("Unexpected GET_CONFIG(key_mgmt): " + key_mgmt)
    dev[0].connect(ssid, psk="12345678", ieee80211w="1",
                   key_mgmt="WPA-PSK WPA-PSK-SHA256", proto="WPA2",
                   scan_freq="2412")
    if "[WPA2-PSK-SHA256-CCMP]" not in dev[0].request("SCAN_RESULTS"):
        raise Exception("Scan results missing RSN element info")
    hwsim_utils.test_connectivity(dev[0], hapd)
    dev[1].connect(ssid, psk="12345678", ieee80211w="2",
                   key_mgmt="WPA-PSK WPA-PSK-SHA256", proto="WPA2",
                   scan_freq="2412")
    hwsim_utils.test_connectivity(dev[1], hapd)
    if "OK" not in hapd.request("SA_QUERY " + dev[0].own_addr()):
        raise Exception("SA_QUERY failed")
    if "OK" not in hapd.request("SA_QUERY " + dev[1].own_addr()):
        raise Exception("SA_QUERY failed")
    if "FAIL" not in hapd.request("SA_QUERY foo"):
        raise Exception("Invalid SA_QUERY accepted")
    wt.require_ap_pmf_mandatory(apdev[0]['bssid'])
    wt.require_sta_pmf(apdev[0]['bssid'], dev[0].p2p_interface_addr())
    wt.require_sta_pmf_mandatory(apdev[0]['bssid'], dev[1].p2p_interface_addr())
    time.sleep(0.1)
    if wt.get_sta_counter("valid_saqueryresp_tx", apdev[0]['bssid'],
                          dev[0].p2p_interface_addr()) < 1:
        raise Exception("STA did not reply to SA Query")
    if wt.get_sta_counter("valid_saqueryresp_tx", apdev[0]['bssid'],
                          dev[1].p2p_interface_addr()) < 1:
        raise Exception("STA did not reply to SA Query")

def start_ocv_ap(apdev):
    ssid = "test-pmf-required"
    params = hostapd.wpa2_params(ssid=ssid, passphrase="12345678")
    params["wpa_key_mgmt"] = "WPA-PSK-SHA256"
    params["ieee80211w"] = "2"
    params["ocv"] = "1"
    try:
        hapd = hostapd.add_ap(apdev, params)
    except Exception as e:
        if "Failed to set hostapd parameter ocv" in str(e):
            raise HwsimSkip("OCV not supported")
        raise

    Wlantest.setup(hapd)
    wt = Wlantest()
    wt.flush()
    wt.add_passphrase("12345678")

    return hapd, ssid, wt

@remote_compatible
def test_ocv_sa_query(dev, apdev):
    """Test SA Query with OCV"""
    hapd, ssid, wt = start_ocv_ap(apdev[0])
    dev[0].connect(ssid, psk="12345678", ieee80211w="1", ocv="1",
                   key_mgmt="WPA-PSK WPA-PSK-SHA256", proto="WPA2",
                   scan_freq="2412")
    hapd.wait_sta() # wait so we can actually request SA_QUERY
    # Test that client can handle SA Query with OCI element
    if "OK" not in hapd.request("SA_QUERY " + dev[0].own_addr()):
        raise Exception("SA_QUERY failed")
    ev = hapd.wait_event(["OCV-FAILURE"], timeout=0.1)
    if ev:
        raise Exception("Unexpected OCV failure reported")
    if wt.get_sta_counter("valid_saqueryresp_tx", apdev[0]['bssid'],
                          dev[0].own_addr()) < 1:
        raise Exception("STA did not reply to SA Query")

    # Test that AP can handle SA Query with OCI element
    if "OK" not in dev[0].request("UNPROT_DEAUTH"):
        raise Exception("Triggering SA Query from the STA failed")
    ev = dev[0].wait_event(["CTRL-EVENT-DISCONNECTED"], timeout=3)
    if ev is not None:
        raise Exception("SA Query from the STA failed")

@remote_compatible
def test_ocv_sa_query_csa(dev, apdev):
    """Test SA Query with OCV after channel switch"""
    hapd, ssid, wt = start_ocv_ap(apdev[0])
    dev[0].connect(ssid, psk="12345678", ieee80211w="1", ocv="1",
                   key_mgmt="WPA-PSK WPA-PSK-SHA256", proto="WPA2",
                   scan_freq="2412")

    hapd.request("CHAN_SWITCH 5 2437 ht")
    time.sleep(1)
    if wt.get_sta_counter("valid_saqueryreq_tx", apdev[0]['bssid'],
                          dev[0].own_addr()) < 1:
        raise Exception("STA did not start SA Query after channel switch")

    ev = dev[0].wait_event(["CTRL-EVENT-DISCONNECTED"], timeout=16)
    if ev is not None:
        raise Exception("Unexpected disconnection")

def test_ocv_sa_query_csa_no_resp(dev, apdev):
    """Test SA Query with OCV after channel switch getting no response"""
    hapd, ssid, wt = start_ocv_ap(apdev[0])
    dev[0].connect(ssid, psk="12345678", ieee80211w="1", ocv="1",
                   key_mgmt="WPA-PSK WPA-PSK-SHA256", proto="WPA2",
                   scan_freq="2412")

    hapd.set("ext_mgmt_frame_handling", "1")
    hapd.request("CHAN_SWITCH 5 2437 ht")
    ev = dev[0].wait_event(["CTRL-EVENT-DISCONNECTED"], timeout=5)
    if ev is None:
        raise Exception("Disconnection after CSA not reported")
    if "locally_generated=1" not in ev:
        raise Exception("Unexpectedly disconnected by AP: " + ev)

def test_ocv_sa_query_csa_missing(dev, apdev):
    """Test SA Query with OCV missing after channel switch"""
    hapd, ssid, wt = start_ocv_ap(apdev[0])
    dev[0].connect(ssid, psk="12345678", ieee80211w="1", ocv="1",
                   key_mgmt="WPA-PSK WPA-PSK-SHA256", proto="WPA2",
                   scan_freq="2412")
    hapd.wait_sta() # wait so kernel won't drop deauth frame (MFP)
    hapd.set("ext_mgmt_frame_handling", "1")
    dev[0].request("DISCONNECT")
    dev[0].wait_disconnected()
    ev = hapd.wait_event(['MGMT-RX'], timeout=5)
    if ev is None:
        raise Exception("Deauthentication frame RX not reported")
    hapd.set("ext_mgmt_frame_handling", "0")
    hapd.request("CHAN_SWITCH 5 2437 ht")
    ev = hapd.wait_event(["AP-STA-DISCONNECTED"], timeout=20)
    if ev is None:
        raise Exception("No disconnection event received from hostapd")

@remote_compatible
def test_ap_pmf_optional(dev, apdev):
    """WPA2-PSK AP with PMF optional"""
    ssid = "test-pmf-optional"
    params = hostapd.wpa2_params(ssid=ssid, passphrase="12345678")
    params["wpa_key_mgmt"] = "WPA-PSK"
    params["ieee80211w"] = "1"
    hapd = hostapd.add_ap(apdev[0], params)
    Wlantest.setup(hapd)
    wt = Wlantest()
    wt.flush()
    wt.add_passphrase("12345678")
    dev[0].connect(ssid, psk="12345678", ieee80211w="1",
                   key_mgmt="WPA-PSK WPA-PSK-SHA256", proto="WPA2",
                   scan_freq="2412")
    hwsim_utils.test_connectivity(dev[0], hapd)
    dev[1].connect(ssid, psk="12345678", ieee80211w="2",
                   key_mgmt="WPA-PSK WPA-PSK-SHA256", proto="WPA2",
                   scan_freq="2412")
    hwsim_utils.test_connectivity(dev[1], hapd)
    wt.require_ap_pmf_optional(apdev[0]['bssid'])
    wt.require_sta_pmf(apdev[0]['bssid'], dev[0].p2p_interface_addr())
    wt.require_sta_pmf_mandatory(apdev[0]['bssid'], dev[1].p2p_interface_addr())

@remote_compatible
def test_ap_pmf_optional_2akm(dev, apdev):
    """WPA2-PSK AP with PMF optional (2 AKMs)"""
    ssid = "test-pmf-optional-2akm"
    params = hostapd.wpa2_params(ssid=ssid, passphrase="12345678")
    params["wpa_key_mgmt"] = "WPA-PSK WPA-PSK-SHA256"
    params["ieee80211w"] = "1"
    hapd = hostapd.add_ap(apdev[0], params)
    Wlantest.setup(hapd)
    wt = Wlantest()
    wt.flush()
    wt.add_passphrase("12345678")
    dev[0].connect(ssid, psk="12345678", ieee80211w="1",
                   key_mgmt="WPA-PSK WPA-PSK-SHA256", proto="WPA2",
                   scan_freq="2412")
    hwsim_utils.test_connectivity(dev[0], hapd)
    dev[1].connect(ssid, psk="12345678", ieee80211w="2",
                   key_mgmt="WPA-PSK WPA-PSK-SHA256", proto="WPA2",
                   scan_freq="2412")
    hwsim_utils.test_connectivity(dev[1], hapd)
    wt.require_ap_pmf_optional(apdev[0]['bssid'])
    wt.require_sta_pmf(apdev[0]['bssid'], dev[0].p2p_interface_addr())
    wt.require_sta_key_mgmt(apdev[0]['bssid'], dev[0].p2p_interface_addr(),
                            "PSK-SHA256")
    wt.require_sta_pmf_mandatory(apdev[0]['bssid'], dev[1].p2p_interface_addr())
    wt.require_sta_key_mgmt(apdev[0]['bssid'], dev[1].p2p_interface_addr(),
                            "PSK-SHA256")

@remote_compatible
def test_ap_pmf_negative(dev, apdev):
    """WPA2-PSK AP without PMF (negative test)"""
    ssid = "test-pmf-negative"
    params = hostapd.wpa2_params(ssid=ssid, passphrase="12345678")
    hapd = hostapd.add_ap(apdev[0], params)
    Wlantest.setup(hapd)
    wt = Wlantest()
    wt.flush()
    wt.add_passphrase("12345678")
    dev[0].connect(ssid, psk="12345678", ieee80211w="1",
                   key_mgmt="WPA-PSK WPA-PSK-SHA256", proto="WPA2",
                   scan_freq="2412")
    hwsim_utils.test_connectivity(dev[0], hapd)
    try:
        dev[1].connect(ssid, psk="12345678", ieee80211w="2",
                       key_mgmt="WPA-PSK WPA-PSK-SHA256", proto="WPA2",
                       scan_freq="2412")
        hwsim_utils.test_connectivity(dev[1], hapd)
        raise Exception("PMF required STA connected to no PMF AP")
    except Exception as e:
        logger.debug("Ignore expected exception: " + str(e))
    wt.require_ap_no_pmf(apdev[0]['bssid'])

@remote_compatible
def test_ap_pmf_assoc_comeback(dev, apdev):
    """WPA2-PSK AP with PMF association comeback"""
    run_ap_pmf_assoc_comeback(dev, apdev)

def test_ap_pmf_assoc_comeback_10000tu(dev, apdev):
    """WPA2-PSK AP with PMF association comeback (10000 TUs)"""
    run_ap_pmf_assoc_comeback(dev, apdev, comeback=10000)

def run_ap_pmf_assoc_comeback(dev, apdev, comeback=None):
    ssid = "assoc-comeback"
    params = hostapd.wpa2_params(ssid=ssid, passphrase="12345678")
    params["wpa_key_mgmt"] = "WPA-PSK-SHA256"
    params["ieee80211w"] = "2"
    if comeback is not None:
        params["assoc_sa_query_max_timeout"] = str(comeback)
    hapd = hostapd.add_ap(apdev[0], params)
    Wlantest.setup(hapd)
    wt = Wlantest()
    wt.flush()
    wt.add_passphrase("12345678")
    dev[0].connect(ssid, psk="12345678", ieee80211w="1",
                   key_mgmt="WPA-PSK WPA-PSK-SHA256", proto="WPA2",
                   scan_freq="2412")
    hapd.wait_sta(wait_4way_hs=True)
    hapd.set("ext_mgmt_frame_handling", "1")
    dev[0].request("DISCONNECT")
    dev[0].wait_disconnected(timeout=10)
    ev = hapd.wait_event(["MGMT-RX"], timeout=1)
    if ev is None:
        raise Exception("Deauthentication frame RX not reported")
    hapd.set("ext_mgmt_frame_handling", "0")
    dev[0].request("REASSOCIATE")
    dev[0].wait_connected(timeout=20, error="Timeout on re-connection")
    hapd.wait_4way_hs()
    if wt.get_sta_counter("assocresp_comeback", apdev[0]['bssid'],
                          dev[0].p2p_interface_addr()) < 1:
        raise Exception("AP did not use association comeback request")

def test_ap_pmf_assoc_comeback_in_wpas(dev, apdev):
    """WPA2-PSK AP with PMF association comeback in wpa_supplicant"""
    ssid = "assoc-comeback"
    params = hostapd.wpa2_params(ssid=ssid, passphrase="12345678")
    params["wpa_key_mgmt"] = "WPA-PSK-SHA256"
    params["ieee80211w"] = "2"
    params["test_assoc_comeback_type"] = "255"
    hapd = hostapd.add_ap(apdev[0], params)

    dev[0].set("test_assoc_comeback_type", "255")
    dev[0].connect(ssid, psk="12345678", ieee80211w="1",
                   key_mgmt="WPA-PSK WPA-PSK-SHA256", proto="WPA2",
                   scan_freq="2412")
    hapd.wait_sta(wait_4way_hs=True)
    hapd.set("ext_mgmt_frame_handling", "1")
    dev[0].request("DISCONNECT")
    dev[0].wait_disconnected(timeout=10)
    ev = hapd.wait_event(["MGMT-RX"], timeout=1)
    if ev is None:
        raise Exception("Deauthentication frame RX not reported")
    hapd.set("ext_mgmt_frame_handling", "0")
    dev[0].request("REASSOCIATE")
    ev = dev[0].wait_event(["CTRL-EVENT-ASSOC-REJECT"], timeout=10)
    if ev is None or "status_code=30" not in ev:
        raise Exception("Association comeback not requested")
    ev = dev[0].wait_event(["CTRL-EVENT-CONNECTED",
                            "CTRL-EVENT-ASSOC-REJECT"], timeout=10)
    if ev is None:
        raise Exception("Association not reported")
    if "CTRL-EVENT-ASSOC-REJECT" in ev:
        raise Exception("Unexpected association rejection: " + ev)
    hapd.wait_4way_hs()

    hapd.set("ext_mgmt_frame_handling", "1")
    dev[0].request("DISCONNECT")
    dev[0].wait_disconnected(timeout=10)
    ev = hapd.wait_event(["MGMT-RX"], timeout=1)
    if ev is None:
        raise Exception("Deauthentication frame RX not reported")
    hapd.set("ext_mgmt_frame_handling", "0")
    dev[0].set("test_assoc_comeback_type", "254")
    dev[0].request("REASSOCIATE")
    ev = dev[0].wait_event(["CTRL-EVENT-ASSOC-REJECT"], timeout=10)
    if ev is None or "status_code=30" not in ev:
        raise Exception("Association comeback not requested")
    ev = dev[0].wait_event(["SME: Temporary assoc reject: missing association comeback time",
                            "CTRL-EVENT-CONNECTED",
                            "CTRL-EVENT-ASSOC-REJECT"], timeout=10)
    if ev is None:
        raise Exception("Association not reported")
    if "SME: Temporary assoc reject: missing association comeback time" not in ev:
        raise Exception("Unexpected result: " + ev)
    dev[0].wait_connected(timeout=20, error="Timeout on re-connection with misbehaving AP")
    hapd.wait_4way_hs()

@remote_compatible
def test_ap_pmf_assoc_comeback2(dev, apdev):
    """WPA2-PSK AP with PMF association comeback (using DROP_SA)"""
    ssid = "assoc-comeback"
    params = hostapd.wpa2_params(ssid=ssid, passphrase="12345678")
    params["wpa_key_mgmt"] = "WPA-PSK"
    params["ieee80211w"] = "1"
    hapd = hostapd.add_ap(apdev[0], params)
    Wlantest.setup(hapd)
    wt = Wlantest()
    wt.flush()
    wt.add_passphrase("12345678")
    dev[0].connect(ssid, psk="12345678", ieee80211w="2",
                   key_mgmt="WPA-PSK", proto="WPA2", scan_freq="2412")
    if "OK" not in dev[0].request("DROP_SA"):
        raise Exception("DROP_SA failed")
    dev[0].request("REASSOCIATE")
    dev[0].wait_connected(timeout=10, error="Timeout on re-connection")
    if wt.get_sta_counter("reassocresp_comeback", apdev[0]['bssid'],
                          dev[0].p2p_interface_addr()) < 1:
        raise Exception("AP did not use reassociation comeback request")

@remote_compatible
def test_ap_pmf_assoc_comeback3(dev, apdev):
    """WPA2-PSK AP with PMF association comeback (using radio_disabled)"""
    drv_flags = dev[0].get_driver_status_field("capa.flags")
    if int(drv_flags, 0) & 0x20 == 0:
        raise HwsimSkip("Driver does not support radio_disabled")
    ssid = "assoc-comeback"
    params = hostapd.wpa2_params(ssid=ssid, passphrase="12345678")
    params["wpa_key_mgmt"] = "WPA-PSK"
    params["ieee80211w"] = "1"
    hapd = hostapd.add_ap(apdev[0], params)
    Wlantest.setup(hapd)
    wt = Wlantest()
    wt.flush()
    wt.add_passphrase("12345678")
    dev[0].connect(ssid, psk="12345678", ieee80211w="2",
                   key_mgmt="WPA-PSK", proto="WPA2", scan_freq="2412")
    dev[0].set("radio_disabled", "1")
    dev[0].set("radio_disabled", "0")
    dev[0].request("REASSOCIATE")
    dev[0].wait_connected(timeout=10, error="Timeout on re-connection")
    if wt.get_sta_counter("assocresp_comeback", apdev[0]['bssid'],
                          dev[0].own_addr()) < 1:
        raise Exception("AP did not use reassociation comeback request")

@remote_compatible
def test_ap_pmf_assoc_comeback_wps(dev, apdev):
    """WPA2-PSK AP with PMF association comeback (WPS)"""
    ssid = "assoc-comeback"
    appin = "12345670"
    params = hostapd.wpa2_params(ssid=ssid, passphrase="12345678")
    params["wpa_key_mgmt"] = "WPA-PSK-SHA256"
    params["ieee80211w"] = "2"
    params["eap_server"] = "1"
    params["wps_state"] = "2"
    params["ap_pin"] = appin
    hapd = hostapd.add_ap(apdev[0], params)
    Wlantest.setup(hapd)
    wt = Wlantest()
    wt.flush()
    wt.add_passphrase("12345678")
    dev[0].connect(ssid, psk="12345678", ieee80211w="1",
                   key_mgmt="WPA-PSK WPA-PSK-SHA256", proto="WPA2",
                   scan_freq="2412")
    hapd.wait_sta(wait_4way_hs=True)
    hapd.set("ext_mgmt_frame_handling", "1")
    dev[0].request("DISCONNECT")
    dev[0].wait_disconnected(timeout=10)
    ev = hapd.wait_event(["MGMT-RX"], timeout=1)
    if ev is None:
        raise Exception("Deauthentication frame RX not reported")
    hapd.set("ext_mgmt_frame_handling", "0")
    dev[0].wps_reg(apdev[0]['bssid'], appin)
    hapd.wait_4way_hs()
    if wt.get_sta_counter("assocresp_comeback", apdev[0]['bssid'],
                          dev[0].p2p_interface_addr()) < 1:
        raise Exception("AP did not use association comeback request")

def test_ap_pmf_ap_dropping_sa(dev, apdev):
    """WPA2-PSK PMF AP dropping SA"""
    ssid = "pmf"
    params = hostapd.wpa2_params(ssid=ssid, passphrase="12345678")
    params["wpa_key_mgmt"] = "WPA-PSK-SHA256"
    params["ieee80211w"] = "2"
    hapd = hostapd.add_ap(apdev[0], params)
    bssid = hapd.own_addr()
    Wlantest.setup(hapd)
    wt = Wlantest()
    wt.flush()
    wt.add_passphrase("12345678")
    dev[0].connect(ssid, psk="12345678", ieee80211w="2",
                   key_mgmt="WPA-PSK-SHA256", proto="WPA2", scan_freq="2412")
    addr0 = dev[0].own_addr()
    dev[0].dump_monitor()
    hapd.wait_sta()
    # Drop SA and association at the AP locally without notifying the STA. This
    # results in the STA getting unprotected Deauthentication frames when trying
    # to transmit the next Class 3 frame.
    if "OK" not in hapd.request("DEAUTHENTICATE " + addr0 + " tx=0"):
        raise Exception("DEAUTHENTICATE command failed")
    ev = dev[0].wait_event(["CTRL-EVENT-DISCONNECTED"], timeout=1)
    if ev is not None:
        raise Exception("Unexpected disconnection event after DEAUTHENTICATE tx=0: " + ev)
    dev[0].request("DATA_TEST_CONFIG 1")
    dev[0].request("DATA_TEST_TX " + bssid + " " + addr0)
    ev = dev[0].wait_event(["CTRL-EVENT-DISCONNECTED"], timeout=5)
    dev[0].request("DATA_TEST_CONFIG 0")
    if ev is None or "locally_generated=1" not in ev:
        raise Exception("Locally generated disconnection not reported")

def test_ap_pmf_known_sta_id(dev, apdev):
    """WPA2-PSK AP and Known STA Identification to avoid association comeback"""
    ssid = "assoc-comeback"
    params = hostapd.wpa2_params(ssid=ssid, passphrase="12345678")
    params["wpa_key_mgmt"] = "WPA-PSK-SHA256"
    params["ieee80211w"] = "2"
    params["known_sta_identification"] = "1"
    hapd = hostapd.add_ap(apdev[0], params)
    Wlantest.setup(hapd)
    wt = Wlantest()
    wt.flush()
    wt.add_passphrase("12345678")
    dev[0].connect(ssid, psk="12345678", ieee80211w="2",
                   key_mgmt="WPA-PSK-SHA256", proto="WPA2",
                   scan_freq="2412")
    hapd.wait_sta(wait_4way_hs=True)
    hapd.set("ext_mgmt_frame_handling", "1")
    dev[0].request("DISCONNECT")
    dev[0].wait_disconnected(timeout=10)
    ev = hapd.wait_event(["MGMT-RX"], timeout=1)
    if ev is None:
        raise Exception("Deauthentication frame RX not reported")
    hapd.set("ext_mgmt_frame_handling", "0")
    dev[0].request("REASSOCIATE")
    dev[0].wait_connected(timeout=20, error="Timeout on re-connection")
    hapd.wait_4way_hs()
    if wt.get_sta_counter("assocresp_comeback", apdev[0]['bssid'],
                          dev[0].own_addr()) > 0:
        raise Exception("AP used association comeback request")

def test_ap_pmf_valid_broadcast_deauth(dev, apdev):
    """WPA2-PSK PMF AP sending valid broadcast deauth without dropping SA"""
    run_ap_pmf_valid(dev, apdev, False, True)

def test_ap_pmf_valid_broadcast_disassoc(dev, apdev):
    """WPA2-PSK PMF AP sending valid broadcast disassoc without dropping SA"""
    run_ap_pmf_valid(dev, apdev, True, True)

def test_ap_pmf_valid_unicast_deauth(dev, apdev):
    """WPA2-PSK PMF AP sending valid unicast deauth without dropping SA"""
    run_ap_pmf_valid(dev, apdev, False, False)

def test_ap_pmf_valid_unicast_disassoc(dev, apdev):
    """WPA2-PSK PMF AP sending valid unicast disassoc without dropping SA"""
    run_ap_pmf_valid(dev, apdev, True, False)

def run_ap_pmf_valid(dev, apdev, disassociate, broadcast):
    ssid = "pmf"
    params = hostapd.wpa2_params(ssid=ssid, passphrase="12345678")
    params["wpa_key_mgmt"] = "WPA-PSK-SHA256"
    params["ieee80211w"] = "2"
    hapd = hostapd.add_ap(apdev[0], params)
    bssid = hapd.own_addr()
    Wlantest.setup(hapd)
    wt = Wlantest()
    wt.flush()
    wt.add_passphrase("12345678")
    dev[0].connect(ssid, psk="12345678", ieee80211w="2",
                   key_mgmt="WPA-PSK-SHA256", proto="WPA2", scan_freq="2412")
    addr0 = dev[0].own_addr()
    dev[0].dump_monitor()
    hapd.wait_sta()
    cmd = "DISASSOCIATE " if disassociate else "DEAUTHENTICATE "
    cmd += "ff:ff:ff:ff:ff:ff" if broadcast else addr0
    cmd += " test=1"
    if "OK" not in hapd.request(cmd):
        raise Exception("hostapd command failed")
    sta = hapd.get_sta(addr0)
    if not sta:
        raise Exception("STA entry lost")
    ev = dev[0].wait_event(["CTRL-EVENT-DISCONNECTED"], timeout=5)
    if ev is None:
        raise Exception("Disconnection not reported")
    if "locally_generated=1" in ev:
        raise Exception("Unexpected locally generated disconnection")

    # Wait for SA Query procedure to fail and association comeback to succeed
    dev[0].wait_connected()

def start_wpas_ap(ssid):
    wpas = WpaSupplicant(global_iface='/tmp/wpas-wlan5')
    wpas.interface_add("wlan5")
    id = wpas.add_network()
    wpas.set_network(id, "mode", "2")
    wpas.set_network_quoted(id, "ssid", ssid)
    wpas.set_network(id, "proto", "WPA2")
    wpas.set_network(id, "key_mgmt", "WPA-PSK-SHA256")
    wpas.set_network(id, "ieee80211w", "2")
    wpas.set_network_quoted(id, "psk", "12345678")
    wpas.set_network(id, "pairwise", "CCMP")
    wpas.set_network(id, "group", "CCMP")
    wpas.set_network(id, "frequency", "2412")
    wpas.set_network(id, "scan_freq", "2412")
    wpas.connect_network(id)
    wpas.dump_monitor()
    return wpas

def test_ap_pmf_sta_sa_query(dev, apdev):
    """WPA2-PSK AP with station using SA Query"""
    ssid = "assoc-comeback"
    addr = dev[0].own_addr()

    wpas = start_wpas_ap(ssid)
    bssid = wpas.own_addr()

    Wlantest.setup(wpas)
    wt = Wlantest()
    wt.flush()
    wt.add_passphrase("12345678")

    dev[0].connect(ssid, psk="12345678", ieee80211w="1",
                   key_mgmt="WPA-PSK WPA-PSK-SHA256", proto="WPA2",
                   scan_freq="2412")
    wpas.dump_monitor()
    wpas.request("DEAUTHENTICATE " + addr + " test=0")
    wpas.dump_monitor()
    wpas.request("DISASSOCIATE " + addr + " test=0")
    wpas.dump_monitor()
    ev = dev[0].wait_event(["CTRL-EVENT-DISCONNECTED"], timeout=1)
    if ev is not None:
        raise Exception("Unexpected disconnection")

    wpas.request("DEAUTHENTICATE " + addr + " reason=6 test=0")
    wpas.dump_monitor()
    wpas.request("DISASSOCIATE " + addr + " reason=7 test=0")
    wpas.dump_monitor()
    ev = dev[0].wait_event(["CTRL-EVENT-DISCONNECTED"], timeout=1)
    if ev is not None:
        raise Exception("Unexpected disconnection")
    if wt.get_sta_counter("valid_saqueryreq_tx", bssid, addr) < 1:
        raise Exception("STA did not send SA Query")
    if wt.get_sta_counter("valid_saqueryresp_rx", bssid, addr) < 1:
        raise Exception("AP did not reply to SA Query")
    wpas.dump_monitor()

def test_ap_pmf_sta_sa_query_no_response(dev, apdev):
    """WPA2-PSK AP with station using SA Query and getting no response"""
    ssid = "assoc-comeback"
    addr = dev[0].own_addr()

    wpas = start_wpas_ap(ssid)
    bssid = wpas.own_addr()

    dev[0].connect(ssid, psk="12345678", ieee80211w="1",
                   key_mgmt="WPA-PSK WPA-PSK-SHA256", proto="WPA2",
                   scan_freq="2412")
    wpas.dump_monitor()
    wpas.request("DEAUTHENTICATE " + addr + " test=0")
    wpas.dump_monitor()
    wpas.request("DISASSOCIATE " + addr + " test=0")
    wpas.dump_monitor()
    ev = dev[0].wait_event(["CTRL-EVENT-DISCONNECTED"], timeout=1)
    if ev is not None:
        raise Exception("Unexpected disconnection")

    wpas.request("SET ext_mgmt_frame_handling 1")
    wpas.request("DEAUTHENTICATE " + addr + " reason=6 test=0")
    wpas.dump_monitor()
    wpas.request("DISASSOCIATE " + addr + " reason=7 test=0")
    wpas.dump_monitor()
    dev[0].wait_disconnected()
    wpas.dump_monitor()
    wpas.request("SET ext_mgmt_frame_handling 0")
    dev[0].wait_connected()
    wpas.dump_monitor()

def test_ap_pmf_sta_unprot_deauth_burst(dev, apdev):
    """WPA2-PSK AP with station receiving burst of unprotected Deauthentication frames"""
    ssid = "deauth-attack"
    addr = dev[0].own_addr()

    wpas = start_wpas_ap(ssid)
    bssid = wpas.own_addr()

    Wlantest.setup(wpas)
    wt = Wlantest()
    wt.flush()
    wt.add_passphrase("12345678")

    dev[0].connect(ssid, psk="12345678", ieee80211w="1",
                   key_mgmt="WPA-PSK WPA-PSK-SHA256", proto="WPA2",
                   scan_freq="2412")

    for i in range(0, 10):
        wpas.request("DEAUTHENTICATE " + addr + " reason=6 test=0")
        wpas.request("DISASSOCIATE " + addr + " reason=7 test=0")
    ev = dev[0].wait_event(["CTRL-EVENT-DISCONNECTED"], timeout=1)
    if ev is not None:
        raise Exception("Unexpected disconnection")
    num_req = wt.get_sta_counter("valid_saqueryreq_tx", bssid, addr)
    num_resp = wt.get_sta_counter("valid_saqueryresp_rx", bssid, addr)
    if num_req < 1:
        raise Exception("STA did not send SA Query")
    if num_resp < 1:
        raise Exception("AP did not reply to SA Query")
    if num_req > 1:
        raise Exception("STA initiated too many SA Query procedures (%d)" % num_req)

    time.sleep(10)
    for i in range(0, 5):
        wpas.request("DEAUTHENTICATE " + addr + " reason=6 test=0")
        wpas.request("DISASSOCIATE " + addr + " reason=7 test=0")
    ev = dev[0].wait_event(["CTRL-EVENT-DISCONNECTED"], timeout=1)
    if ev is not None:
        raise Exception("Unexpected disconnection")
    num_req = wt.get_sta_counter("valid_saqueryreq_tx", bssid, addr)
    num_resp = wt.get_sta_counter("valid_saqueryresp_rx", bssid, addr)
    if num_req != 2 or num_resp != 2:
        raise Exception("Unexpected number of SA Query procedures (req=%d resp=%d)" % (num_req, num_resp))

def test_ap_pmf_sta_sa_query_oom(dev, apdev):
    """WPA2-PSK AP with station using SA Query (OOM)"""
    ssid = "assoc-comeback"
    addr = dev[0].own_addr()
    wpas = start_wpas_ap(ssid)
    dev[0].connect(ssid, psk="12345678", ieee80211w="1",
                   key_mgmt="WPA-PSK WPA-PSK-SHA256", proto="WPA2",
                   scan_freq="2412")
    with alloc_fail(dev[0], 1, "=sme_sa_query_timer"):
        wpas.request("DEAUTHENTICATE " + addr + " reason=6 test=0")
        wait_fail_trigger(dev[0], "GET_ALLOC_FAIL")
    dev[0].request("DISCONNECT")
    wpas.request("DISCONNECT")
    dev[0].wait_disconnected()

def test_ap_pmf_sta_sa_query_local_failure(dev, apdev):
    """WPA2-PSK AP with station using SA Query (local failure)"""
    ssid = "assoc-comeback"
    addr = dev[0].own_addr()
    wpas = start_wpas_ap(ssid)
    dev[0].connect(ssid, psk="12345678", ieee80211w="1",
                   key_mgmt="WPA-PSK WPA-PSK-SHA256", proto="WPA2",
                   scan_freq="2412")
    with fail_test(dev[0], 1, "os_get_random;sme_sa_query_timer"):
        wpas.request("DEAUTHENTICATE " + addr + " reason=6 test=0")
        wait_fail_trigger(dev[0], "GET_FAIL")
    dev[0].request("DISCONNECT")
    wpas.request("DISCONNECT")
    dev[0].wait_disconnected()

def test_ap_pmf_sta_sa_query_hostapd(dev, apdev):
    """WPA2-PSK AP with station using SA Query (hostapd)"""
    ssid = "assoc-comeback"
    passphrase = "12345678"
    addr = dev[0].own_addr()

    params = hostapd.wpa2_params(ssid=ssid, passphrase=passphrase,
                                 wpa_key_mgmt="WPA-PSK-SHA256",
                                 ieee80211w="2")
    hapd = hostapd.add_ap(apdev[0], params)
    bssid = hapd.own_addr()

    Wlantest.setup(hapd)
    wt = Wlantest()
    wt.flush()
    wt.add_passphrase("12345678")

    dev[0].connect(ssid, psk=passphrase, ieee80211w="2",
                   key_mgmt="WPA-PSK-SHA256", proto="WPA2",
                   scan_freq="2412")
    hapd.wait_sta()
    if "OK" not in hapd.request("DEAUTHENTICATE " + addr + " test=0") or \
       "OK" not in hapd.request("DISASSOCIATE " + addr + " test=0"):
        raise Exception("Failed to send unprotected disconnection messages")
    ev = dev[0].wait_event(["CTRL-EVENT-DISCONNECTED"], timeout=1)
    if ev is not None:
        raise Exception("Unexpected disconnection")

    if "OK" not in hapd.request("DEAUTHENTICATE " + addr + " reason=6 test=0") or \
       "OK" not in hapd.request("DISASSOCIATE " + addr + " reason=7 test=0"):
        raise Exception("Failed to send unprotected disconnection messages (2)")
    ev = dev[0].wait_event(["CTRL-EVENT-DISCONNECTED"], timeout=1)
    if ev is not None:
        raise Exception("Unexpected disconnection")
    if wt.get_sta_counter("valid_saqueryreq_tx", bssid, addr) < 1:
        raise Exception("STA did not send SA Query")
    if wt.get_sta_counter("valid_saqueryresp_rx", bssid, addr) < 1:
        raise Exception("AP did not reply to SA Query")

def test_ap_pmf_sta_sa_query_no_response_hostapd(dev, apdev):
    """WPA2-PSK AP with station using SA Query and getting no response (hostapd)"""
    ssid = "assoc-comeback"
    passphrase = "12345678"
    addr = dev[0].own_addr()

    params = hostapd.wpa2_params(ssid=ssid, passphrase=passphrase,
                                 wpa_key_mgmt="WPA-PSK-SHA256",
                                 ieee80211w="2")
    hapd = hostapd.add_ap(apdev[0], params)
    bssid = hapd.own_addr()

    Wlantest.setup(hapd)
    wt = Wlantest()
    wt.flush()
    wt.add_passphrase("12345678")

    dev[0].connect(ssid, psk=passphrase, ieee80211w="2",
                   key_mgmt="WPA-PSK-SHA256", proto="WPA2",
                   scan_freq="2412")
    hapd.wait_sta()
    hapd.set("ext_mgmt_frame_handling", "1")
    if "OK" not in hapd.request("DEAUTHENTICATE " + addr + " reason=6 test=0") or \
       "OK" not in hapd.request("DISASSOCIATE " + addr + " reason=7 test=0"):
        raise Exception("Failed to send unprotected disconnection messages")
    dev[0].wait_disconnected()
    hapd.set("ext_mgmt_frame_handling", "0")
    if wt.get_sta_counter("valid_saqueryreq_tx", bssid, addr) < 1:
        raise Exception("STA did not send SA Query")
    if wt.get_sta_counter("valid_saqueryresp_rx", bssid, addr) > 0:
        raise Exception("AP replied to SA Query")
    dev[0].wait_connected()

def test_ap_pmf_sta_unprot_deauth_burst_hostapd(dev, apdev):
    """WPA2-PSK AP with station receiving burst of unprotected Deauthentication frames (hostapd)"""
    ssid = "deauth-attack"
    passphrase = "12345678"
    addr = dev[0].own_addr()

    params = hostapd.wpa2_params(ssid=ssid, passphrase=passphrase,
                                 wpa_key_mgmt="WPA-PSK-SHA256",
                                 ieee80211w="2")
    hapd = hostapd.add_ap(apdev[0], params)
    bssid = hapd.own_addr()

    Wlantest.setup(hapd)
    wt = Wlantest()
    wt.flush()
    wt.add_passphrase("12345678")

    dev[0].connect(ssid, psk=passphrase, ieee80211w="2",
                   key_mgmt="WPA-PSK-SHA256", proto="WPA2",
                   scan_freq="2412")
    hapd.wait_sta()
    for i in range(10):
        if "OK" not in hapd.request("DEAUTHENTICATE " + addr + " reason=6 test=0") or \
           "OK" not in hapd.request("DISASSOCIATE " + addr + " reason=7 test=0"):
            raise Exception("Failed to send unprotected disconnection messages")
    ev = dev[0].wait_event(["CTRL-EVENT-DISCONNECTED"], timeout=1)
    if ev is not None:
        raise Exception("Unexpected disconnection")
    num_req = wt.get_sta_counter("valid_saqueryreq_tx", bssid, addr)
    num_resp = wt.get_sta_counter("valid_saqueryresp_rx", bssid, addr)
    if num_req < 1:
        raise Exception("STA did not send SA Query")
    if num_resp < 1:
        raise Exception("AP did not reply to SA Query")
    if num_req > 1:
        raise Exception("STA initiated too many SA Query procedures (%d)" % num_req)

    time.sleep(10)
    for i in range(5):
        if "OK" not in hapd.request("DEAUTHENTICATE " + addr + " reason=6 test=0") or \
           "OK" not in hapd.request("DISASSOCIATE " + addr + " reason=7 test=0"):
            raise Exception("Failed to send unprotected disconnection messages")
    ev = dev[0].wait_event(["CTRL-EVENT-DISCONNECTED"], timeout=1)
    if ev is not None:
        raise Exception("Unexpected disconnection")
    num_req = wt.get_sta_counter("valid_saqueryreq_tx", bssid, addr)
    num_resp = wt.get_sta_counter("valid_saqueryresp_rx", bssid, addr)
    if num_req != 2 or num_resp != 2:
        raise Exception("Unexpected number of SA Query procedures (req=%d resp=%d)" % (num_req, num_resp))

def test_ap_pmf_required_eap(dev, apdev):
    """WPA2-EAP AP with PMF required"""
    ssid = "test-pmf-required-eap"
    params = hostapd.wpa2_eap_params(ssid=ssid)
    params["wpa_key_mgmt"] = "WPA-EAP-SHA256"
    params["ieee80211w"] = "2"
    hapd = hostapd.add_ap(apdev[0], params)
    key_mgmt = hapd.get_config()['key_mgmt']
    if key_mgmt.split(' ')[0] != "WPA-EAP-SHA256":
        raise Exception("Unexpected GET_CONFIG(key_mgmt): " + key_mgmt)
    dev[0].connect("test-pmf-required-eap", key_mgmt="WPA-EAP-SHA256",
                   ieee80211w="2", eap="PSK", identity="psk.user@example.com",
                   password_hex="0123456789abcdef0123456789abcdef",
                   scan_freq="2412")
    dev[1].connect("test-pmf-required-eap", key_mgmt="WPA-EAP WPA-EAP-SHA256",
                   ieee80211w="1", eap="PSK", identity="psk.user@example.com",
                   password_hex="0123456789abcdef0123456789abcdef",
                   scan_freq="2412")

def test_ap_pmf_optional_eap(dev, apdev):
    """WPA2EAP AP with PMF optional"""
    params = hostapd.wpa2_eap_params(ssid="test-wpa2-eap")
    params["ieee80211w"] = "1"
    hapd = hostapd.add_ap(apdev[0], params)
    dev[0].connect("test-wpa2-eap", key_mgmt="WPA-EAP", eap="TTLS",
                   identity="pap user", anonymous_identity="ttls",
                   password="password",
                   ca_cert="auth_serv/ca.pem", phase2="auth=PAP",
                   ieee80211w="1", scan_freq="2412")
    dev[1].connect("test-wpa2-eap", key_mgmt="WPA-EAP WPA-EAP-SHA256",
                   eap="TTLS", identity="pap user", anonymous_identity="ttls",
                   password="password",
                   ca_cert="auth_serv/ca.pem", phase2="auth=PAP",
                   ieee80211w="2", scan_freq="2412")

@remote_compatible
def test_ap_pmf_required_sha1(dev, apdev):
    """WPA2-PSK AP with PMF required with SHA1 AKM"""
    ssid = "test-pmf-required-sha1"
    params = hostapd.wpa2_params(ssid=ssid, passphrase="12345678")
    params["wpa_key_mgmt"] = "WPA-PSK"
    params["ieee80211w"] = "2"
    hapd = hostapd.add_ap(apdev[0], params)
    Wlantest.setup(hapd)
    wt = Wlantest()
    wt.flush()
    wt.add_passphrase("12345678")
    key_mgmt = hapd.get_config()['key_mgmt']
    if key_mgmt.split(' ')[0] != "WPA-PSK":
        raise Exception("Unexpected GET_CONFIG(key_mgmt): " + key_mgmt)
    dev[0].connect(ssid, psk="12345678", ieee80211w="2",
                   key_mgmt="WPA-PSK", proto="WPA2", scan_freq="2412")
    if "[WPA2-PSK-CCMP]" not in dev[0].request("SCAN_RESULTS"):
        raise Exception("Scan results missing RSN element info")
    hwsim_utils.test_connectivity(dev[0], hapd)

@remote_compatible
def test_ap_pmf_toggle(dev, apdev):
    """WPA2-PSK AP with PMF optional and changing PMF on reassociation"""
    try:
        _test_ap_pmf_toggle(dev, apdev)
    finally:
        dev[0].request("SET reassoc_same_bss_optim 0")

def _test_ap_pmf_toggle(dev, apdev):
    ssid = "test-pmf-optional"
    params = hostapd.wpa2_params(ssid=ssid, passphrase="12345678")
    params["wpa_key_mgmt"] = "WPA-PSK"
    params["ieee80211w"] = "1"
    params["assoc_sa_query_max_timeout"] = "1"
    params["assoc_sa_query_retry_timeout"] = "1"
    hapd = hostapd.add_ap(apdev[0], params)
    Wlantest.setup(hapd)
    wt = Wlantest()
    wt.flush()
    wt.add_passphrase("12345678")
    bssid = apdev[0]['bssid']
    addr = dev[0].own_addr()
    dev[0].request("SET reassoc_same_bss_optim 1")
    id = dev[0].connect(ssid, psk="12345678", ieee80211w="1",
                        key_mgmt="WPA-PSK WPA-PSK-SHA256", proto="WPA2",
                        scan_freq="2412")
    wt.require_ap_pmf_optional(bssid)
    wt.require_sta_pmf(bssid, addr)
    sta = hapd.get_sta(addr)
    if '[MFP]' not in sta['flags']:
        raise Exception("MFP flag not present for STA")

    dev[0].set_network(id, "ieee80211w", "0")
    dev[0].request("REASSOCIATE")
    dev[0].wait_connected()
    wt.require_sta_no_pmf(bssid, addr)
    sta = hapd.get_sta(addr)
    if '[MFP]' in sta['flags']:
        raise Exception("MFP flag unexpectedly present for STA")
    err, data = hapd.cmd_execute(['iw', 'dev', apdev[0]['ifname'], 'station',
                                  'get', addr])
    if "yes" in [l for l in data.splitlines() if "MFP" in l][0]:
        raise Exception("Kernel STA entry had MFP enabled")

    dev[0].set_network(id, "ieee80211w", "1")
    dev[0].request("REASSOCIATE")
    dev[0].wait_connected()
    wt.require_sta_pmf(bssid, addr)
    sta = hapd.get_sta(addr)
    if '[MFP]' not in sta['flags']:
        raise Exception("MFP flag not present for STA")
    err, data = hapd.cmd_execute(['iw', 'dev', apdev[0]['ifname'], 'station',
                                  'get', addr])
    if "yes" not in [l for l in data.splitlines() if "MFP" in l][0]:
        raise Exception("Kernel STA entry did not have MFP enabled")

@remote_compatible
def test_ap_pmf_required_sta_no_pmf(dev, apdev):
    """WPA2-PSK AP with PMF required and PMF disabled on STA"""
    ssid = "test-pmf-required"
    params = hostapd.wpa2_params(ssid=ssid, passphrase="12345678")
    params["wpa_key_mgmt"] = "WPA-PSK-SHA256"
    params["ieee80211w"] = "2"
    hapd = hostapd.add_ap(apdev[0], params)

    # Disable PMF on the station and try to connect
    dev[0].connect(ssid, psk="12345678", ieee80211w="0",
                   key_mgmt="WPA-PSK WPA-PSK-SHA256", proto="WPA2",
                   scan_freq="2412", wait_connect=False)
    ev = dev[0].wait_event(["CTRL-EVENT-NETWORK-NOT-FOUND",
                            "CTRL-EVENT-ASSOC-REJECT"], timeout=2)
    if ev is None:
        raise Exception("No connection result")
    if "CTRL-EVENT-ASSOC-REJECT" in ev:
        raise Exception("Tried to connect to PMF required AP without PMF enabled")
    dev[0].request("REMOVE_NETWORK all")

def test_ap_pmf_inject_auth(dev, apdev):
    """WPA2-PSK AP with PMF and Authentication frame injection"""
    ssid = "test-pmf"
    params = hostapd.wpa2_params(ssid=ssid, passphrase="12345678")
    params["wpa_key_mgmt"] = "WPA-PSK-SHA256"
    params["ieee80211w"] = "2"
    hapd = hostapd.add_ap(apdev[0], params)
    dev[0].connect(ssid, psk="12345678", ieee80211w="2",
                   key_mgmt="WPA-PSK-SHA256", proto="WPA2",
                   scan_freq="2412")
    hapd.wait_sta()
    hwsim_utils.test_connectivity(dev[0], hapd)

    bssid = hapd.own_addr().replace(':', '')
    addr = dev[0].own_addr().replace(':', '')

    # Inject an unprotected Authentication frame claiming to be from the
    # associated STA, from another STA, from the AP's own address, from all
    # zeros and all ones addresses, and from a multicast address.
    hapd.request("SET ext_mgmt_frame_handling 1")
    failed = False
    addresses = [ addr, "021122334455", bssid, 6*"00", 6*"ff", 6*"01" ]
    for a in addresses:
        auth = "b0003a01" + bssid + a + bssid + '1000000001000000'
        res = hapd.request("MGMT_RX_PROCESS freq=2412 datarate=0 ssi_signal=-30 frame=%s" % auth)
        if "OK" not in res:
            failed = True
    hapd.request("SET ext_mgmt_frame_handling 0")
    if failed:
        raise Exception("MGMT_RX_PROCESS failed")
    time.sleep(0.1)

    ev = dev[0].wait_event(["CTRL-EVENT-DISCONNECTED"], timeout=0.1)
    if ev:
        raise Exception("Unexpected disconnection reported on the STA")

    # Verify that original association is still functional.
    hwsim_utils.test_connectivity(dev[0], hapd)

    # Inject an unprotected Association Request frame (with and without RSNE)
    # claiming to be from the set of test addresses.
    hapd.request("SET ext_mgmt_frame_handling 1")
    for a in addresses:
        assoc = "00003a01" + bssid + a + bssid + '2000' + '31040500' + '0008746573742d706d66' + '010802040b160c121824' + '301a0100000fac040100000fac040100000fac06c0000000000fac06'
        res = hapd.request("MGMT_RX_PROCESS freq=2412 datarate=0 ssi_signal=-30 frame=%s" % assoc)
        if "OK" not in res:
            failed = True

        assoc = "00003a01" + bssid + a + bssid + '2000' + '31040500' + '0008746573742d706d66' + '010802040b160c121824' + '3000'
        res = hapd.request("MGMT_RX_PROCESS freq=2412 datarate=0 ssi_signal=-30 frame=%s" % assoc)
        if "OK" not in res:
            failed = True

        assoc = "00003a01" + bssid + a + bssid + '2000' + '31040500' + '0008746573742d706d66' + '010802040b160c121824'
        res = hapd.request("MGMT_RX_PROCESS freq=2412 datarate=0 ssi_signal=-30 frame=%s" % assoc)
        if "OK" not in res:
            failed = True
    hapd.request("SET ext_mgmt_frame_handling 0")
    if failed:
        raise Exception("MGMT_RX_PROCESS failed")
    time.sleep(5)

    ev = dev[0].wait_event(["CTRL-EVENT-DISCONNECTED"], timeout=0.1)
    if ev:
        raise Exception("Unexpected disconnection reported on the STA")

    # Verify that original association is still functional.
    hwsim_utils.test_connectivity(dev[0], hapd)

def test_ap_pmf_inject_assoc(dev, apdev):
    """WPA2-PSK with PMF and Association Request frame injection"""
    run_ap_pmf_inject_assoc(dev, apdev, False)

def test_ap_pmf_inject_assoc_wps(dev, apdev):
    """WPA2-PSK/WPS with PMF and Association Request frame injection"""
    run_ap_pmf_inject_assoc(dev, apdev, True)

def inject_assoc_req(hapd, addr, frame):
    hapd.set("ext_mgmt_frame_handling", "1")
    res = hapd.request("MGMT_RX_PROCESS freq=2412 datarate=0 ssi_signal=-30 frame=%s" % frame)
    if "OK" not in res:
        raise Exception("MGMT_RX_PROCESS failed")
    hapd.set("ext_mgmt_frame_handling", "0")
    sta = hapd.get_sta(addr)
    if "[MFP]" not in sta['flags']:
        raise Exception("MFP flag removed")
    if sta["AKMSuiteSelector"] != '00-0f-ac-6':
        raise Exception("AKMSuiteSelector value changed")

def run_ap_pmf_inject_assoc(dev, apdev, wps):
    ssid = "test-pmf"
    params = hostapd.wpa2_params(ssid=ssid, passphrase="12345678")
    params["wpa_key_mgmt"] = "WPA-PSK WPA-PSK-SHA256"
    params["ieee80211w"] = "1"
    if wps:
        params["eap_server"] = "1"
        params["wps_state"] = "2"

    hapd = hostapd.add_ap(apdev[0], params)
    dev[0].connect(ssid, psk="12345678", ieee80211w="2",
                   key_mgmt="WPA-PSK-SHA256", proto="WPA2",
                   scan_freq="2412")
    hapd.wait_sta()
    sta = hapd.get_sta(dev[0].own_addr())
    if "[MFP]" not in sta['flags']:
        raise Exception("MFP flag not reported")
    if sta["AKMSuiteSelector"] != '00-0f-ac-6':
        raise Exception("Incorrect AKMSuiteSelector value")

    bssid = hapd.own_addr().replace(':', '')
    addr = dev[0].own_addr().replace(':', '')

    # Inject unprotected Association Request frames
    assoc1 = "00003a01" + bssid + addr + bssid + '2000' + '31040500' + '0008746573742d706d66' + '010802040b160c121824' + '30140100000fac040100000fac040100000fac020000'
    assoc2 = "00003a01" + bssid + addr + bssid + '2000' + '31040500' + '0008746573742d706d66' + '010802040b160c121824' + '30140100000fac040100000fac040100000fac060000'
    assoc3 = "00003a01" + bssid + addr + bssid + '2000' + '31040500' + '0008746573742d706d66' + '010802040b160c121824'

    inject_assoc_req(hapd, dev[0].own_addr(), assoc1)
    time.sleep(0.1)
    inject_assoc_req(hapd, dev[0].own_addr(), assoc1)
    time.sleep(0.1)
    inject_assoc_req(hapd, dev[0].own_addr(), assoc2)
    time.sleep(0.1)
    inject_assoc_req(hapd, dev[0].own_addr(), assoc3)
    time.sleep(0.1)
    inject_assoc_req(hapd, dev[0].own_addr(), assoc2)

    ev = dev[0].wait_event(["CTRL-EVENT-DISCONNECTED"], timeout=5.1)
    if ev:
        raise Exception("Unexpected disconnection reported on the STA")
    ev = hapd.wait_event(["AP-STA-DISCONNECTED"], timeout=0.1)
    if ev:
        raise Exception("Unexpected disconnection event received from hostapd")

    # Verify that original association is still functional.
    hwsim_utils.test_connectivity(dev[0], hapd)

def test_ap_pmf_inject_data(dev, apdev):
    """WPA2-PSK AP with PMF and Data frame injection"""
    try:
        run_ap_pmf_inject_data(dev, apdev)
    finally:
        stop_monitor(apdev[1]["ifname"])

def run_ap_pmf_inject_data(dev, apdev):
    ssid = "test-pmf"
    params = hostapd.wpa2_params(ssid=ssid, passphrase="12345678")
    params["wpa_key_mgmt"] = "WPA-PSK-SHA256"
    params["ieee80211w"] = "2"
    hapd = hostapd.add_ap(apdev[0], params)
    dev[0].connect(ssid, psk="12345678", ieee80211w="2",
                   key_mgmt="WPA-PSK-SHA256", proto="WPA2",
                   scan_freq="2412")
    hapd.wait_sta()
    hwsim_utils.test_connectivity(dev[0], hapd)

    sock = start_monitor(apdev[1]["ifname"])
    radiotap = radiotap_build()

    bssid = hapd.own_addr().replace(':', '')
    addr = dev[0].own_addr().replace(':', '')

    # Inject Data frame with A2=broadcast, A2=multicast, A2=BSSID, A2=STA, and
    # A2=unknown unicast
    addresses = [ 6*"ff", 6*"01", bssid, addr, "020102030405" ]
    for a in addresses:
        frame = binascii.unhexlify("48010000" + bssid + a + bssid + "0000")
        sock.send(radiotap + frame)

    time.sleep(0.1)
    ev = dev[0].wait_event(["CTRL-EVENT-DISCONNECTED"], timeout=0.1)
    if ev:
        raise Exception("Unexpected disconnection reported on the STA")
    hwsim_utils.test_connectivity(dev[0], hapd)

def test_ap_pmf_inject_msg1(dev, apdev):
    """WPA2-PSK AP with PMF and EAPOL-Key msg 1/4 injection"""
    try:
        run_ap_pmf_inject_msg1(dev, apdev)
    finally:
        stop_monitor(apdev[1]["ifname"])

def test_ap_pmf_inject_msg1_no_pmf(dev, apdev):
    """WPA2-PSK AP without PMF and EAPOL-Key msg 1/4 injection"""
    try:
        run_ap_pmf_inject_msg1(dev, apdev, pmf=False)
    finally:
        stop_monitor(apdev[1]["ifname"])

def run_ap_pmf_inject_msg1(dev, apdev, pmf=True):
    ssid = "test-pmf"
    params = hostapd.wpa2_params(ssid=ssid, passphrase="12345678")
    params["wpa_key_mgmt"] = "WPA-PSK-SHA256"
    if pmf:
        params["ieee80211w"] = "2"
    hapd = hostapd.add_ap(apdev[0], params)
    dev[0].connect(ssid, psk="12345678", ieee80211w="2" if pmf else "0",
                   key_mgmt="WPA-PSK-SHA256", proto="WPA2",
                   scan_freq="2412")
    hapd.wait_sta()

    sock = start_monitor(apdev[1]["ifname"])
    radiotap = radiotap_build()

    bssid = hapd.own_addr().replace(':', '')
    addr = dev[0].own_addr().replace(':', '')

    # Inject unprotected EAPOL-Key msg 1/4 with an invalid KDE
    f = "88020000" + addr + bssid + bssid + "0000" + "0700"
    f += "aaaa03000000" + "888e"
    f += "0203006602008b00100000000000000005bcb714da6f98f817b88948485c26ef052922b795814819f1889ae01e11b486910000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000007" + "dd33000fac0400"
    frame = binascii.unhexlify(f)
    sock.send(radiotap + frame)

    ev = dev[0].wait_event(["CTRL-EVENT-DISCONNECTED"], timeout=0.5)
    if ev:
        raise Exception("Unexpected disconnection reported on the STA")
    hwsim_utils.test_connectivity(dev[0], hapd)
    state = dev[0].get_status_field("wpa_state")
    if state != "COMPLETED":
        raise Exception("Unexpected wpa_state: " + state)

def test_ap_pmf_inject_eap(dev, apdev):
    """WPA2-EAP AP with PMF and EAP frame injection"""
    try:
        run_ap_pmf_inject_eap(dev, apdev)
    finally:
        stop_monitor(apdev[1]["ifname"])

def run_ap_pmf_inject_eap(dev, apdev, pmf=True):
    ssid = "test-pmf-eap"
    params = hostapd.wpa2_eap_params(ssid=ssid)
    params["wpa_key_mgmt"] = "WPA-EAP-SHA256"
    params["ieee80211w"] = "2"
    hapd = hostapd.add_ap(apdev[0], params)
    dev[0].connect(ssid, key_mgmt="WPA-EAP-SHA256",
                   ieee80211w="2", eap="PSK", identity="psk.user@example.com",
                   password_hex="0123456789abcdef0123456789abcdef",
                   scan_freq="2412")
    hapd.wait_sta()
    dev[0].dump_monitor()
    hapd.dump_monitor()

    sock = start_monitor(apdev[1]["ifname"])
    radiotap = radiotap_build()

    bssid = hapd.own_addr().replace(':', '')
    addr = dev[0].own_addr().replace(':', '')

    disconnected = False
    eap_start = False
    eap_failure = False
    ap_disconnected = False

    # Inject various unexpected unprotected EAPOL frames to the STA
    f = "88020000" + addr + bssid + bssid + "0000" + "0700"
    f += "aaaa03000000" + "888e"
    tests = []
    for i in range(101):
        tests += [ "02000005012d000501" ] # EAP-Request/Identity
    for i in range(101):
        tests += [ "02000022012e00222f00862406a9b45782fee8a62e837457d1367365727665722e77312e6669" ] # EAP-Request/PSK
    tests += [ "0200000404780004" ] # EAP-Failure
    tests += [ "0200000403780004" ] # EAP-Success
    tests += [ "02000006057800060100" ] # EAP-Initiate
    tests += [ "0200000406780004" ] # EAP-Finish
    tests += [ "0200000400780004" ] # EAP-?
    tests += [ "02020000" ] # EAPOL-Logoff
    tests += [ "02010000" ] # EAPOL-Start
    for t in tests:
        dev[0].note("Inject " + t)
        frame = binascii.unhexlify(f + t)
        sock.send(radiotap + frame)
        for i in range(2):
            ev = dev[0].wait_event(["CTRL-EVENT-DISCONNECTED",
                                    "CTRL-EVENT-EAP-STARTED",
                                    "CTRL-EVENT-EAP-FAILURE"],
                                   timeout=0.0001)
            if ev is None:
                break
            if "CTRL-EVENT-DISCONNECTED" in ev:
                disconnected = True
            if "CTRL-EVENT-EAP-START" in ev:
                eap_start = True
            if "CTRL-EVENT-EAP-FAILURE" in ev:
                eap_failure = True
        dev[0].dump_monitor(mon=False)
    dev[0].dump_monitor()
    ev = hapd.wait_event(["AP-STA-DISCONNECTED"], timeout=0.1)
    if ev:
        ap_disconnected = True
    if disconnected or eap_start or eap_failure or ap_disconnected:
        raise Exception("Unexpected event:%s%s%s%s" %
                        (" disconnected" if disconnected else "",
                         " eap_start" if eap_start else "",
                         " eap_failure" if eap_failure else "",
                         " ap_disconnected" if ap_disconnected else ""))
    hwsim_utils.test_connectivity(dev[0], hapd)
    state = dev[0].get_status_field("wpa_state")
    if state != "COMPLETED":
        raise Exception("Unexpected wpa_state: " + state)

    dev[0].dump_monitor()
    hapd.dump_monitor()

    # Inject various unexpected unprotected EAPOL frames to the AP
    f = "88010000" + bssid + addr + bssid + "0000" + "0700"
    f += "aaaa03000000" + "888e"
    tests = []
    tests += [ "02020000" ] # EAPOL-Logoff
    for i in range(10):
        tests += [ "02010000" ] # EAPOL-Start
    for t in tests:
        hapd.note("Inject " + t)
        frame = binascii.unhexlify(f + t)
        sock.send(radiotap + frame)
        for i in range(2):
            ev = dev[0].wait_event(["CTRL-EVENT-DISCONNECTED",
                                    "CTRL-EVENT-EAP-STARTED",
                                    "CTRL-EVENT-EAP-FAILURE"],
                                   timeout=0.0001)
            if ev is None:
                break
            if "CTRL-EVENT-DISCONNECTED" in ev:
                disconnected = True
            if "CTRL-EVENT-EAP-START" in ev:
                eap_start = True
            if "CTRL-EVENT-EAP-FAILURE" in ev:
                eap_failure = True
        dev[0].dump_monitor(mon=False)
    dev[0].dump_monitor()
    ev = hapd.wait_event(["AP-STA-DISCONNECTED"], timeout=0.1)
    if ev:
        ap_disconnected = True
    hapd.dump_monitor()
    if disconnected or eap_start or eap_failure or ap_disconnected:
        raise Exception("Unexpected event(2):%s%s%s%s" %
                        (" disconnected" if disconnected else "",
                         " eap_start" if eap_start else "",
                         " eap_failure" if eap_failure else "",
                         " ap_disconnected" if ap_disconnected else ""))
    hwsim_utils.test_connectivity(dev[0], hapd)
    state = dev[0].get_status_field("wpa_state")
    if state != "COMPLETED":
        raise Exception("Unexpected wpa_state(2): " + state)

def test_ap_pmf_tkip_reject(dev, apdev):
    """Mixed mode BSS and MFP-enabled AP rejecting TKIP"""
    skip_without_tkip(dev[0])
    params = hostapd.wpa2_params(ssid="test-pmf", passphrase="12345678")
    params['wpa'] = '3'
    params["ieee80211w"] = "1"
    params["wpa_pairwise"] = "TKIP CCMP"
    params["rsn_pairwise"] = "TKIP CCMP"
    hostapd.add_ap(apdev[0], params)

    dev[0].connect("test-pmf", psk="12345678", pairwise="CCMP", ieee80211w="2",
                   scan_freq="2412")
    dev[0].dump_monitor()

    dev[1].connect("test-pmf", psk="12345678", proto="WPA", pairwise="TKIP",
                   ieee80211w="0", scan_freq="2412")
    dev[1].dump_monitor()

    dev[2].connect("test-pmf", psk="12345678", pairwise="TKIP",
                   ieee80211w="2", scan_freq="2412", wait_connect=False)
    ev = dev[2].wait_event(["CTRL-EVENT-CONNECTED",
                            "CTRL-EVENT-ASSOC-REJECT"], timeout=10)
    if ev is None:
        raise Exception("No connection result reported")
    if "CTRL-EVENT-ASSOC-REJECT" not in ev:
        raise Exception("MFP + TKIP connection was not rejected")
    if "status_code=31" not in ev:
        raise Exception("Unexpected status code in rejection: " + ev)
    dev[2].request("DISCONNECT")
    dev[2].dump_monitor()

def test_ap_pmf_sa_query_timeout(dev, apdev):
    """SA Query timeout"""
    ssid = "test-pmf-required"
    params = hostapd.wpa2_params(ssid=ssid, passphrase="12345678")
    params["wpa_key_mgmt"] = "WPA-PSK-SHA256"
    params["ieee80211w"] = "2"
    hapd = hostapd.add_ap(apdev[0], params)
    dev[0].connect(ssid, psk="12345678", ieee80211w="2",
                   key_mgmt="WPA-PSK-SHA256", proto="WPA2",
                   scan_freq="2412")

    hapd.set("ext_mgmt_frame_handling", "1")
    if "OK" not in dev[0].request("UNPROT_DEAUTH"):
        raise Exception("Triggering SA Query from the STA failed")
    ev = dev[0].wait_event(["CTRL-EVENT-DISCONNECTED"], timeout=2)
    if ev is None:
        raise Exception("No disconnection on SA Query timeout seen")
    hapd.set("ext_mgmt_frame_handling", "0")
    dev[0].wait_connected()
    dev[0].dump_monitor()

    hapd.set("ext_mgmt_frame_handling", "1")
    if "OK" not in dev[0].request("UNPROT_DEAUTH"):
        raise Exception("Triggering SA Query from the STA failed")
    ev = hapd.mgmt_rx()
    hapd.set("ext_mgmt_frame_handling", "0")
    dev[0].request("DISCONNECT")
    dev[0].wait_disconnected()
    dev[0].request("RECONNECT")
    dev[0].wait_connected()
    hapd.set("ext_mgmt_frame_handling", "1")
    ev = dev[0].wait_event(["CTRL-EVENT-DISCONNECTED"], timeout=1.5)
    if ev is not None:
        raise Exception("Unexpected disconnection after reconnection seen")

def mac80211_read_key(keydir):
    vals = {}
    for name in os.listdir(keydir):
        try:
            with open(os.path.join(keydir, name)) as f:
                vals[name] = f.read().strip()
        except OSError as e:
            pass
    return vals

def check_mac80211_bigtk(dev, hapd):
    sta_key = None
    ap_key = None

    phy = dev.get_driver_status_field("phyname")
    keys = "/sys/kernel/debug/ieee80211/%s/keys" % phy
    try:
        for key in os.listdir(keys):
            keydir = os.path.join(keys, key)
            vals = mac80211_read_key(keydir)
            keyidx = int(vals['keyidx'])
            if keyidx == 6 or keyidx == 7:
                sta_key = vals;
                break
    except OSError as e:
        raise HwsimSkip("debugfs not supported in mac80211 (STA)")

    phy = hapd.get_driver_status_field("phyname")
    keys = "/sys/kernel/debug/ieee80211/%s/keys" % phy
    try:
        for key in os.listdir(keys):
            keydir = os.path.join(keys, key)
            vals = mac80211_read_key(keydir)
            keyidx = int(vals['keyidx'])
            if keyidx == 6 or keyidx == 7:
                ap_key = vals;
                break
    except OSError as e:
        raise HwsimSkip("debugfs not supported in mac80211 (AP)")

    if not sta_key:
        raise Exception("Could not find STA key information from debugfs")
    logger.info("STA key: " + str(sta_key))

    if not ap_key:
        raise Exception("Could not find AP key information from debugfs")
    logger.info("AP key: " + str(ap_key))

    if sta_key['key'] != ap_key['key']:
        raise Exception("AP and STA BIGTK mismatch")

    if sta_key['keyidx'] != ap_key['keyidx']:
        raise Exception("AP and STA BIGTK keyidx mismatch")

    if sta_key['algorithm'] != ap_key['algorithm']:
        raise Exception("AP and STA BIGTK algorithm mismatch")

    replays = int(sta_key['replays'])
    icverrors = int(sta_key['icverrors'])
    if replays > 0 or icverrors > 0:
        raise Exception("STA reported errors: replays=%d icverrors=%d" % replays, icverrors)

    rx_spec = int(sta_key['rx_spec'], base=16)
    if rx_spec < 3:
        raise Exception("STA did not update BIGTK receive counter sufficiently")

    tx_spec = int(ap_key['tx_spec'], base=16)
    if tx_spec < 3:
        raise Exception("AP did not update BIGTK BIPN sufficiently")

def test_ap_pmf_beacon_protection_bip(dev, apdev):
    """WPA2-PSK Beacon protection (BIP)"""
    run_ap_pmf_beacon_protection(dev, apdev, "AES-128-CMAC")

def test_ap_pmf_beacon_protection_bip_cmac_256(dev, apdev):
    """WPA2-PSK Beacon protection (BIP-CMAC-256)"""
    run_ap_pmf_beacon_protection(dev, apdev, "BIP-CMAC-256")

def test_ap_pmf_beacon_protection_bip_gmac_128(dev, apdev):
    """WPA2-PSK Beacon protection (BIP-GMAC-128)"""
    run_ap_pmf_beacon_protection(dev, apdev, "BIP-GMAC-128")

def test_ap_pmf_beacon_protection_bip_gmac_256(dev, apdev):
    """WPA2-PSK Beacon protection (BIP-GMAC-256)"""
    run_ap_pmf_beacon_protection(dev, apdev, "BIP-GMAC-256")

def run_ap_pmf_beacon_protection(dev, apdev, cipher):
    ssid = "test-beacon-prot"
    params = hostapd.wpa2_params(ssid=ssid, passphrase="12345678")
    params["wpa_key_mgmt"] = "WPA-PSK-SHA256"
    params["ieee80211w"] = "2"
    params["beacon_prot"] = "1"
    params["group_mgmt_cipher"] = cipher
    try:
        hapd = hostapd.add_ap(apdev[0], params)
    except Exception as e:
        if "Failed to enable hostapd interface" in str(e):
            raise HwsimSkip("Beacon protection not supported")
        raise

    bssid = hapd.own_addr()

    Wlantest.setup(hapd)
    wt = Wlantest()
    wt.flush()
    wt.add_passphrase("12345678")

    dev[0].flush_scan_cache()

    # STA with Beacon protection enabled
    dev[0].connect(ssid, psk="12345678", ieee80211w="2", beacon_prot="1",
                   key_mgmt="WPA-PSK-SHA256", proto="WPA2", scan_freq="2412")
    if dev[0].get_status_field("bigtk_set") != "1":
        raise Exception("bigtk_set=1 not indicated")

    # STA with Beacon protection disabled
    dev[1].connect(ssid, psk="12345678", ieee80211w="2",
                   key_mgmt="WPA-PSK-SHA256", proto="WPA2", scan_freq="2412")
    if dev[1].get_status_field("bigtk_set") == "1":
        raise Exception("Unexpected bigtk_set=1 indication")

    time.sleep(1)
    check_mac80211_bigtk(dev[0], hapd)

    valid_bip = wt.get_bss_counter('valid_bip_mmie', bssid)
    invalid_bip = wt.get_bss_counter('invalid_bip_mmie', bssid)
    missing_bip = wt.get_bss_counter('missing_bip_mmie', bssid)
    logger.info("wlantest BIP counters: valid=%d invalid=%d missing=%d" % (valid_bip, invalid_bip, missing_bip))
    if valid_bip < 0 or invalid_bip > 0 or missing_bip > 0:
        raise Exception("Unexpected wlantest BIP counters: valid=%d invalid=%d missing=%d" % (valid_bip, invalid_bip, missing_bip))

    ev = dev[0].wait_event(["CTRL-EVENT-BEACON-LOSS"], timeout=10)
    if ev is not None:
        raise Exception("Beacon loss detected")

    # Verify that the SSID has been successfully verified from a protected
    # Beacon frame.
    if dev[0].get_status_field("ssid_verified") != "1":
        raise Exception("ssid_verified=1 not in STATUS")

def test_ap_pmf_beacon_protection_mismatch(dev, apdev):
    """WPA2-PSK Beacon protection MIC mismatch"""
    run_ap_pmf_beacon_protection_mismatch(dev, apdev, False)

def test_ap_pmf_beacon_protection_missing(dev, apdev):
    """WPA2-PSK Beacon protection MME missing"""
    run_ap_pmf_beacon_protection_mismatch(dev, apdev, True)

def run_ap_pmf_beacon_protection_mismatch(dev, apdev, clear):
    ssid = "test-beacon-prot"
    params = hostapd.wpa2_params(ssid=ssid, passphrase="12345678")
    params["wpa_key_mgmt"] = "WPA-PSK-SHA256"
    params["ieee80211w"] = "2"
    params["beacon_prot"] = "1"
    params["group_mgmt_cipher"] = "AES-128-CMAC"
    try:
        hapd = hostapd.add_ap(apdev[0], params)
    except Exception as e:
        if "Failed to enable hostapd interface" in str(e):
            raise HwsimSkip("Beacon protection not supported")
        raise

    bssid = hapd.own_addr()

    Wlantest.setup(hapd)
    wt = Wlantest()
    wt.flush()
    wt.add_passphrase("12345678")

    dev[0].connect(ssid, psk="12345678", ieee80211w="2", beacon_prot="1",
                   key_mgmt="WPA-PSK-SHA256", proto="WPA2", scan_freq="2412")

    WPA_ALG_NONE = 0
    WPA_ALG_IGTK = 4
    KEY_FLAG_DEFAULT = 0x02
    KEY_FLAG_TX = 0x08
    KEY_FLAG_GROUP = 0x10
    KEY_FLAG_GROUP_TX_DEFAULT = KEY_FLAG_GROUP | KEY_FLAG_TX | KEY_FLAG_DEFAULT

    addr = "ff:ff:ff:ff:ff:ff"

    if clear:
        res = hapd.request("SET_KEY %d %s %d %d %s %s %d" % (WPA_ALG_NONE, addr, 6, 1, 6*"00", "", KEY_FLAG_GROUP))
    else:
        res = hapd.request("SET_KEY %d %s %d %d %s %s %d" % (WPA_ALG_IGTK, addr, 6, 1, 6*"00", 16*"00", KEY_FLAG_GROUP_TX_DEFAULT))
    if "OK" not in res:
        raise Exception("SET_KEY failed")

    ev = dev[0].wait_event(["CTRL-EVENT-UNPROT-BEACON"], timeout=5)
    if ev is None:
        raise Exception("Unprotected Beacon frame not reported")

    ev = dev[0].wait_event(["CTRL-EVENT-BEACON-LOSS"], timeout=5)
    if ev is None:
        raise Exception("Beacon loss not reported")

    ev = hapd.wait_event(["CTRL-EVENT-UNPROT-BEACON"], timeout=5)
    if ev is None:
        raise Exception("WNM-Notification Request frame not reported")

def test_ap_pmf_beacon_protection_reconnect(dev, apdev):
    """Beacon protection and reconnection"""
    ssid = "test-beacon-prot"
    params = hostapd.wpa2_params(ssid=ssid, passphrase="12345678")
    params["wpa_key_mgmt"] = "WPA-PSK-SHA256"
    params["ieee80211w"] = "2"
    params["beacon_prot"] = "1"
    params["group_mgmt_cipher"] = "AES-128-CMAC"
    try:
        hapd = hostapd.add_ap(apdev[0], params)
    except Exception as e:
        if "Failed to enable hostapd interface" in str(e):
            raise HwsimSkip("Beacon protection not supported")
        raise

    dev[0].connect(ssid, psk="12345678", ieee80211w="2", beacon_prot="1",
                   key_mgmt="WPA-PSK-SHA256", proto="WPA2", scan_freq="2412")
    dev[0].request("DISCONNECT")
    dev[0].wait_disconnected()
    dev[0].request("RECONNECT")
    dev[0].wait_connected()
    time.sleep(1)
    check_mac80211_bigtk(dev[0], hapd)
    ev = dev[0].wait_event(["CTRL-EVENT-BEACON-LOSS"], timeout=5)
    if ev is not None:
        raise Exception("Beacon loss detected")

def test_ap_pmf_beacon_protection_unicast(dev, apdev):
    """WPA2-PSK Beacon protection (BIP) and unicast Beacon frame"""
    try:
        run_ap_pmf_beacon_protection_unicast(dev, apdev)
    finally:
        stop_monitor(apdev[1]["ifname"])

def run_ap_pmf_beacon_protection_unicast(dev, apdev):
    cipher = "AES-128-CMAC"
    ssid = "test-beacon-prot"
    params = hostapd.wpa2_params(ssid=ssid, passphrase="12345678")
    params["wpa_key_mgmt"] = "WPA-PSK-SHA256"
    params["ieee80211w"] = "2"
    params["beacon_prot"] = "1"
    params["group_mgmt_cipher"] = cipher
    try:
        hapd = hostapd.add_ap(apdev[0], params)
    except Exception as e:
        if "Failed to enable hostapd interface" in str(e):
            raise HwsimSkip("Beacon protection not supported")
        raise

    bssid = hapd.own_addr()

    Wlantest.setup(hapd)
    wt = Wlantest()
    wt.flush()
    wt.add_passphrase("12345678")

    # STA with Beacon protection enabled
    dev[0].connect(ssid, psk="12345678", ieee80211w="2", beacon_prot="1",
                   key_mgmt="WPA-PSK-SHA256", proto="WPA2", scan_freq="2412")
    hapd.wait_sta()

    sock = start_monitor(apdev[1]["ifname"])
    radiotap = radiotap_build()

    bssid = hapd.own_addr().replace(':', '')
    addr = dev[0].own_addr().replace(':', '')

    h = "80000000" + addr + bssid + bssid + "0000"
    h += "c0a0260d27090600"+ "6400" + "1104"
    h += "0010746573742d626561636f6e2d70726f74"
    h += "010882848b960c121824"
    h += "03010"
    h += "1050400020000"
    h += "2a0104"
    h += "32043048606c"
    h += "30140100000fac040100000fac040100000fac06cc00"
    h += "3b025100"
    h += "2d1a0c001bffff000000000000000000000100000000000000000000"
    h += "3d1601000000000000000000000000000000000000000000"
    h += "7f0b0400000200000040000010"
    h += "2503000b01" # CSA
    h += "3c0400510b01" # ECSA
    h += "dd180050f2020101010003a4000027a4000042435e0062322f00"

    frame = binascii.unhexlify(h)
    h += "4c1006002100000000002b8fab24bcef3bb1" #MME
    frame2 = binascii.unhexlify(h)

    sock.send(radiotap + frame)
    ev = dev[0].wait_event(["CTRL-EVENT-UNPROT-BEACON",
                            "CTRL-EVENT-STARTED-CHANNEL-SWITCH"], timeout=5)
    if ev:
        if "CTRL-EVENT-STARTED-CHANNEL-SWITCH" in ev:
            raise Exception("Unexpected channel switch reported")
        if hapd.own_addr() not in ev:
            raise Exception("Unexpected BSSID in unprotected beacon indication")

    time.sleep(10.1)
    sock.send(radiotap + frame2)
    ev = dev[0].wait_event(["CTRL-EVENT-UNPROT-BEACON",
                            "CTRL-EVENT-STARTED-CHANNEL-SWITCH"], timeout=5)
    if ev:
        if "CTRL-EVENT-STARTED-CHANNEL-SWITCH" in ev:
            raise Exception("Unexpected channel switch reported")
        if hapd.own_addr() not in ev:
            raise Exception("Unexpected BSSID in unprotected beacon indication")

def test_ap_pmf_sta_global_require(dev, apdev):
    """WPA2-PSK AP with PMF optional and wpa_supplicant pmf=2"""
    ssid = "test-pmf-optional"
    params = hostapd.wpa2_params(ssid=ssid, passphrase="12345678")
    params["wpa_key_mgmt"] = "WPA-PSK"
    params["ieee80211w"] = "1"
    hapd = hostapd.add_ap(apdev[0], params)
    try:
        dev[0].set("pmf", "2")
        dev[0].connect(ssid, psk="12345678",
                       key_mgmt="WPA-PSK WPA-PSK-SHA256", proto="WPA2",
                       scan_freq="2412")
        pmf = dev[0].get_status_field("pmf")
        if pmf != "1":
            raise Exception("Unexpected PMF state: " + str(pmf))
    finally:
        dev[0].set("pmf", "0")

def test_ap_pmf_sta_global_require2(dev, apdev):
    """WPA2-PSK AP with PMF optional and wpa_supplicant pmf=2 (2)"""
    ssid = "test-pmf-optional"
    params = hostapd.wpa2_params(ssid=ssid, passphrase="12345678")
    params["wpa_key_mgmt"] = "WPA-PSK"
    params["ieee80211w"] = "0"
    hapd = hostapd.add_ap(apdev[0], params)
    bssid = hapd.own_addr()
    try:
        dev[0].scan_for_bss(bssid, freq=2412)
        dev[0].set("pmf", "2")
        dev[0].connect(ssid, psk="12345678",
                       key_mgmt="WPA-PSK WPA-PSK-SHA256", proto="WPA2",
                       scan_freq="2412", wait_connect=False)
        ev = dev[0].wait_event(["CTRL-EVENT-CONNECTED",
                                "CTRL-EVENT-NETWORK-NOT-FOUND"], timeout=10)
        if ev is None:
            raise Exception("Connection result not reported")
        if "CTRL-EVENT-CONNECTED" in ev:
            raise Exception("Unexpected connection")
    finally:
        dev[0].set("pmf", "0")

def test_ap_pmf_drop_robust_mgmt_prior_to_keys_installation(dev, apdev):
    """Drop non protected Robust Action frames prior to keys installation"""
    ssid = "test-pmf-required"
    passphrase = '12345678'
    params = hostapd.wpa2_params(ssid=ssid, passphrase=passphrase)
    params['delay_eapol_tx'] = '1'
    params['ieee80211w'] = '2'
    params['wpa_pairwise_update_count'] = '5'
    hapd = hostapd.add_ap(apdev[0], params, wait_enabled=False)

    # Spectrum management with Channel Switch element
    msg = {'fc': 0x00d0,
           'sa': hapd.own_addr(),
           'da': dev[0].own_addr(),
           'bssid': hapd.own_addr(),
           'payload': binascii.unhexlify('00042503000608')
           }

    dev[0].connect(ssid, psk=passphrase, scan_freq='2412', ieee80211w='1',
                   wait_connect=False)

    # wait for the first delay before sending the frame
    ev = hapd.wait_event(['DELAY-EAPOL-TX-1'], timeout=10)
    if ev is None:
        raise Exception("EAPOL is not delayed")

    # send the Action frame while connecting (prior to keys installation)
    hapd.mgmt_tx(msg)

    dev[0].wait_connected(timeout=10, error="Timeout on connection")
    hapd.wait_sta()
    hwsim_utils.test_connectivity(dev[0], hapd)

    # Verify no channel switch event
    ev = dev[0].wait_event(['CTRL-EVENT-STARTED-CHANNEL-SWITCH'], timeout=5)
    if ev is not None:
        raise Exception("Unexpected CSA prior to keys installation")

    # Send the frame after keys installation and verify channel switch event
    hapd.mgmt_tx(msg)
    ev = dev[0].wait_event(['CTRL-EVENT-STARTED-CHANNEL-SWITCH'], timeout=5)
    if ev is None:
        raise Exception("Expected CSA handling after keys installation")

def test_ap_pmf_eapol_logoff(dev, apdev):
    """WPA2-EAP AP with PMF required and EAPOL-Logoff"""
    ssid = "test-pmf-required-eap"
    params = hostapd.wpa2_eap_params(ssid=ssid)
    params["wpa_key_mgmt"] = "WPA-EAP-SHA256"
    params["ieee80211w"] = "2"
    hapd = hostapd.add_ap(apdev[0], params)
    hapd.request("SET ext_eapol_frame_io 1")

    dev[0].set("ext_eapol_frame_io", "1")
    dev[0].connect("test-pmf-required-eap", key_mgmt="WPA-EAP-SHA256",
                   ieee80211w="2", eap="PSK", identity="psk.user@example.com",
                   password_hex="0123456789abcdef0123456789abcdef",
                   scan_freq="2412", wait_connect=False)

    # EAP-Request/Identity
    proxy_msg(hapd, dev[0])

    # EAP-Response/Identity RX
    msg = rx_msg(dev[0])
    # EAPOL-Logoff TX (inject)
    tx_msg(dev[0], hapd, "02020000")
    # EAP-Response/Identity TX (proxy previously received)
    tx_msg(dev[0], hapd, msg)

    # Verify that the 10 ms timeout for deauthenticating STA after EAP-Failure
    # is not used in this sequence with the EAPOL-Logoff message before the
    # successful authentication.
    ev = dev[0].wait_event(["CTRL-EVENT-DISCONNECTED"], timeout=0.03)
    if ev:
        raise Exception("Unexpected disconnection")

    # EAP-Request/Identity
    proxy_msg(hapd, dev[0])
    # EAP-Response/Identity
    proxy_msg(dev[0], hapd)

    # EAP-PSK
    proxy_msg(hapd, dev[0])
    proxy_msg(dev[0], hapd)
    proxy_msg(hapd, dev[0])
    proxy_msg(dev[0], hapd)
    proxy_msg(hapd, dev[0])

    # 4-way handshake
    proxy_msg(hapd, dev[0])
    proxy_msg(dev[0], hapd)
    proxy_msg(hapd, dev[0])
    proxy_msg(dev[0], hapd)

    ev = hapd.wait_event(["EAPOL-4WAY-HS-COMPLETED"], timeout=1)
    if ev is None:
        raise Exception("4-way handshake did not complete successfully")
    dev[0].wait_connected(timeout=0.1)
    hapd.wait_sta()

    # Verify that the STA gets disconnected when the EAPOL-Logoff message is
    # sent after successful authentication.

    # EAPOL-Logoff TX (inject)
    tx_msg(dev[0], hapd, "02020000")
    hapd.request("SET ext_eapol_frame_io 0")
    dev[0].set("ext_eapol_frame_io", "0")
    ev = dev[0].wait_disconnected(timeout=1)
    if "reason=23" not in ev:
        raise Exception("Unexpected disconnection reason: " + ev)
