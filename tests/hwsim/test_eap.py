# EAP authentication tests
# Copyright (c) 2019-2024, Jouni Malinen <j@w1.fi>
#
# This software may be distributed under the terms of the BSD license.
# See README for more details.

import logging
logger = logging.getLogger()

import hostapd
from utils import alloc_fail, fail_test, wait_fail_trigger, HwsimSkip
from test_ap_eap import check_eap_capa, int_eap_server_params, eap_connect, \
    eap_reauth

def int_teap_server_params(eap_teap_auth=None,
                           eap_teap_separate_result=None, eap_teap_id=None,
                           eap_teap_method_sequence=None):
    params = int_eap_server_params()
    params['eap_fast_a_id'] = "101112131415161718191a1b1c1dff00"
    params['eap_fast_a_id_info'] = "test server 0"
    if eap_teap_auth:
        params['eap_teap_auth'] = eap_teap_auth
    if eap_teap_separate_result:
        params['eap_teap_separate_result'] = eap_teap_separate_result
    if eap_teap_id:
        params['eap_teap_id'] = eap_teap_id
    if eap_teap_method_sequence:
        params['eap_teap_method_sequence'] = eap_teap_method_sequence
    return params

def test_eap_teap_eap_mschapv2(dev, apdev):
    """EAP-TEAP with inner EAP-MSCHAPv2"""
    check_eap_capa(dev[0], "TEAP")
    check_eap_capa(dev[0], "MSCHAPV2")
    params = hostapd.wpa2_eap_params(ssid="test-wpa2-eap")
    hapd = hostapd.add_ap(apdev[0], params)
    eap_connect(dev[0], hapd, "TEAP", "user",
                anonymous_identity="TEAP", password="password",
                ca_cert="auth_serv/ca.pem", phase2="auth=MSCHAPV2")
    eap_reauth(dev[0], "TEAP")

def test_eap_teap_eap_pwd(dev, apdev):
    """EAP-TEAP with inner EAP-PWD"""
    check_eap_capa(dev[0], "TEAP")
    check_eap_capa(dev[0], "PWD")
    params = hostapd.wpa2_eap_params(ssid="test-wpa2-eap")
    hapd = hostapd.add_ap(apdev[0], params)
    eap_connect(dev[0], hapd, "TEAP", "user-pwd-2",
                anonymous_identity="TEAP", password="password",
                ca_cert="auth_serv/ca.pem", phase2="auth=PWD")

def test_eap_teap_eap_eke(dev, apdev):
    """EAP-TEAP with inner EAP-EKE"""
    check_eap_capa(dev[0], "TEAP")
    check_eap_capa(dev[0], "EKE")
    params = hostapd.wpa2_eap_params(ssid="test-wpa2-eap")
    hapd = hostapd.add_ap(apdev[0], params)
    eap_connect(dev[0], hapd, "TEAP", "user-eke-2",
                anonymous_identity="TEAP", password="password",
                ca_cert="auth_serv/ca.pem", phase2="auth=EKE")

def test_eap_teap_basic_password_auth(dev, apdev):
    """EAP-TEAP with Basic-Password-Auth"""
    check_eap_capa(dev[0], "TEAP")
    params = int_teap_server_params(eap_teap_auth="1")
    hapd = hostapd.add_ap(apdev[0], params)
    eap_connect(dev[0], hapd, "TEAP", "user",
                anonymous_identity="TEAP", password="password",
                ca_cert="auth_serv/ca.pem")

def test_eap_teap_basic_password_auth_failure(dev, apdev):
    """EAP-TEAP with Basic-Password-Auth failure"""
    check_eap_capa(dev[0], "TEAP")
    params = int_teap_server_params(eap_teap_auth="1")
    hapd = hostapd.add_ap(apdev[0], params)
    eap_connect(dev[0], hapd, "TEAP", "user",
                anonymous_identity="TEAP", password="incorrect",
                ca_cert="auth_serv/ca.pem", expect_failure=True)

def test_eap_teap_basic_password_auth_no_password(dev, apdev):
    """EAP-TEAP with Basic-Password-Auth and no password configured"""
    check_eap_capa(dev[0], "TEAP")
    params = int_teap_server_params(eap_teap_auth="1")
    hapd = hostapd.add_ap(apdev[0], params)
    eap_connect(dev[0], hapd, "TEAP", "user",
                anonymous_identity="TEAP",
                ca_cert="auth_serv/ca.pem", expect_failure=True)

def test_eap_teap_basic_password_auth_id0(dev, apdev):
    """EAP-TEAP with Basic-Password-Auth (eap_teap_id=0)"""
    run_eap_teap_basic_password_auth_id(dev, apdev, 0)

def test_eap_teap_basic_password_auth_id1(dev, apdev):
    """EAP-TEAP with Basic-Password-Auth (eap_teap_id=1)"""
    run_eap_teap_basic_password_auth_id(dev, apdev, 1)

def test_eap_teap_basic_password_auth_id2(dev, apdev):
    """EAP-TEAP with Basic-Password-Auth (eap_teap_id=2)"""
    run_eap_teap_basic_password_auth_id(dev, apdev, 2, failure=True)

def test_eap_teap_basic_password_auth_id3(dev, apdev):
    """EAP-TEAP with Basic-Password-Auth (eap_teap_id=3)"""
    run_eap_teap_basic_password_auth_id(dev, apdev, 3)

def test_eap_teap_basic_password_auth_id4(dev, apdev):
    """EAP-TEAP with Basic-Password-Auth (eap_teap_id=4)"""
    run_eap_teap_basic_password_auth_id(dev, apdev, 4)

def run_eap_teap_basic_password_auth_id(dev, apdev, eap_teap_id, failure=False):
    check_eap_capa(dev[0], "TEAP")
    params = int_teap_server_params(eap_teap_auth="1",
                                    eap_teap_id=str(eap_teap_id))
    hapd = hostapd.add_ap(apdev[0], params)
    eap_connect(dev[0], hapd, "TEAP", "user",
                anonymous_identity="TEAP", password="password",
                ca_cert="auth_serv/ca.pem",
                expect_failure=failure)

def test_eap_teap_basic_password_auth_machine(dev, apdev):
    """EAP-TEAP with Basic-Password-Auth using machine credential"""
    check_eap_capa(dev[0], "TEAP")
    params = int_teap_server_params(eap_teap_auth="1", eap_teap_id="2")
    hapd = hostapd.add_ap(apdev[0], params)
    eap_connect(dev[0], hapd, "TEAP", "",
                anonymous_identity="TEAP",
                machine_identity="machine", machine_password="machine-password",
                ca_cert="auth_serv/ca.pem")

def test_eap_teap_basic_password_auth_user_and_machine(dev, apdev):
    """EAP-TEAP with Basic-Password-Auth using user and machine credentials"""
    check_eap_capa(dev[0], "TEAP")
    params = int_teap_server_params(eap_teap_auth="1", eap_teap_id="5")
    hapd = hostapd.add_ap(apdev[0], params)
    eap_connect(dev[0], hapd, "TEAP", "user", password="password",
                anonymous_identity="TEAP",
                machine_identity="machine", machine_password="machine-password",
                ca_cert="auth_serv/ca.pem")

def test_eap_teap_basic_password_auth_user_and_machine_fail_user(dev, apdev):
    """EAP-TEAP with Basic-Password-Auth using user and machine credentials (fail user)"""
    check_eap_capa(dev[0], "TEAP")
    params = int_teap_server_params(eap_teap_auth="1", eap_teap_id="5")
    hapd = hostapd.add_ap(apdev[0], params)
    eap_connect(dev[0], hapd, "TEAP", "user", password="wrong-password",
                anonymous_identity="TEAP",
                machine_identity="machine", machine_password="machine-password",
                ca_cert="auth_serv/ca.pem",
                expect_failure=True)

def test_eap_teap_basic_password_auth_user_and_machine_fail_machine(dev, apdev):
    """EAP-TEAP with Basic-Password-Auth using user and machine credentials (fail machine)"""
    check_eap_capa(dev[0], "TEAP")
    params = int_teap_server_params(eap_teap_auth="1", eap_teap_id="5")
    hapd = hostapd.add_ap(apdev[0], params)
    eap_connect(dev[0], hapd, "TEAP", "user", password="password",
                anonymous_identity="TEAP",
                machine_identity="machine",
                machine_password="wrong-machine-password",
                ca_cert="auth_serv/ca.pem",
                expect_failure=True)

def test_eap_teap_basic_password_auth_user_and_machine_no_machine(dev, apdev):
    """EAP-TEAP with Basic-Password-Auth using user and machine credentials (no machine)"""
    check_eap_capa(dev[0], "TEAP")
    params = int_teap_server_params(eap_teap_auth="1", eap_teap_id="5")
    hapd = hostapd.add_ap(apdev[0], params)
    eap_connect(dev[0], hapd, "TEAP", "user", password="password",
                anonymous_identity="TEAP",
                ca_cert="auth_serv/ca.pem",
                expect_failure=True)

def test_eap_teap_peer_outer_tlvs(dev, apdev):
    """EAP-TEAP with peer Outer TLVs"""
    check_eap_capa(dev[0], "TEAP")
    check_eap_capa(dev[0], "MSCHAPV2")
    params = hostapd.wpa2_eap_params(ssid="test-wpa2-eap")
    hapd = hostapd.add_ap(apdev[0], params)
    eap_connect(dev[0], hapd, "TEAP", "user",
                anonymous_identity="TEAP", password="password",
                ca_cert="auth_serv/ca.pem", phase2="auth=MSCHAPV2",
                phase1="teap_test_outer_tlvs=1")

def test_eap_teap_eap_mschapv2_separate_result(dev, apdev):
    """EAP-TEAP with inner EAP-MSCHAPv2 and separate message for Result TLV"""
    check_eap_capa(dev[0], "TEAP")
    check_eap_capa(dev[0], "MSCHAPV2")
    params = int_teap_server_params(eap_teap_separate_result="1")
    hapd = hostapd.add_ap(apdev[0], params)
    eap_connect(dev[0], hapd, "TEAP", "user",
                anonymous_identity="TEAP", password="password",
                ca_cert="auth_serv/ca.pem", phase2="auth=MSCHAPV2")

def test_eap_teap_eap_mschapv2_id0(dev, apdev):
    """EAP-TEAP with inner EAP-MSCHAPv2 (eap_teap_id=0)"""
    run_eap_teap_eap_mschapv2_id(dev, apdev, 0)

def test_eap_teap_eap_mschapv2_id1(dev, apdev):
    """EAP-TEAP with inner EAP-MSCHAPv2 (eap_teap_id=1)"""
    run_eap_teap_eap_mschapv2_id(dev, apdev, 1)

def test_eap_teap_eap_mschapv2_id2(dev, apdev):
    """EAP-TEAP with inner EAP-MSCHAPv2 (eap_teap_id=2)"""
    run_eap_teap_eap_mschapv2_id(dev, apdev, 2, failure=True)

def test_eap_teap_eap_mschapv2_id3(dev, apdev):
    """EAP-TEAP with inner EAP-MSCHAPv2 (eap_teap_id=3)"""
    run_eap_teap_eap_mschapv2_id(dev, apdev, 3)

def test_eap_teap_eap_mschapv2_id4(dev, apdev):
    """EAP-TEAP with inner EAP-MSCHAPv2 (eap_teap_id=4)"""
    run_eap_teap_eap_mschapv2_id(dev, apdev, 4)

def run_eap_teap_eap_mschapv2_id(dev, apdev, eap_teap_id, failure=False):
    check_eap_capa(dev[0], "TEAP")
    check_eap_capa(dev[0], "MSCHAPV2")
    params = int_teap_server_params(eap_teap_id=str(eap_teap_id))
    hapd = hostapd.add_ap(apdev[0], params)
    eap_connect(dev[0], hapd, "TEAP", "user",
                anonymous_identity="TEAP", password="password",
                ca_cert="auth_serv/ca.pem", phase2="auth=MSCHAPV2",
                expect_failure=failure)

def test_eap_teap_eap_mschapv2_machine(dev, apdev):
    """EAP-TEAP with inner EAP-MSCHAPv2 using machine credential"""
    check_eap_capa(dev[0], "TEAP")
    check_eap_capa(dev[0], "MSCHAPV2")
    params = int_teap_server_params(eap_teap_id="2")
    hapd = hostapd.add_ap(apdev[0], params)
    eap_connect(dev[0], hapd, "TEAP", "",
                anonymous_identity="TEAP",
                machine_identity="machine", machine_password="machine-password",
                ca_cert="auth_serv/ca.pem", phase2="auth=MSCHAPV2")

def test_eap_teap_eap_mschapv2_user_and_machine(dev, apdev):
    """EAP-TEAP with inner EAP-MSCHAPv2 using user and machine credentials"""
    check_eap_capa(dev[0], "TEAP")
    check_eap_capa(dev[0], "MSCHAPV2")
    params = int_teap_server_params(eap_teap_id="5")
    hapd = hostapd.add_ap(apdev[0], params)
    eap_connect(dev[0], hapd, "TEAP", "user", password="password",
                anonymous_identity="TEAP",
                machine_identity="machine", machine_password="machine-password",
                ca_cert="auth_serv/ca.pem", phase2="auth=MSCHAPV2")

def test_eap_teap_eap_mschapv2_user_and_machine_seq1(dev, apdev):
    """EAP-TEAP with inner EAP-MSCHAPv2 using user and machine credentials (seq1)"""
    check_eap_capa(dev[0], "TEAP")
    check_eap_capa(dev[0], "MSCHAPV2")
    params = int_teap_server_params(eap_teap_id="5",
                                    eap_teap_method_sequence="1")
    hapd = hostapd.add_ap(apdev[0], params)
    eap_connect(dev[0], hapd, "TEAP", "user", password="password",
                anonymous_identity="TEAP",
                machine_identity="machine", machine_password="machine-password",
                ca_cert="auth_serv/ca.pem", phase2="auth=MSCHAPV2")

def test_eap_teap_eap_mschapv2_user_and_machine_fail_user(dev, apdev):
    """EAP-TEAP with inner EAP-MSCHAPv2 using user and machine credentials (fail user)"""
    check_eap_capa(dev[0], "TEAP")
    check_eap_capa(dev[0], "MSCHAPV2")
    params = int_teap_server_params(eap_teap_id="5")
    hapd = hostapd.add_ap(apdev[0], params)
    eap_connect(dev[0], hapd, "TEAP", "user", password="wrong-password",
                anonymous_identity="TEAP",
                machine_identity="machine", machine_password="machine-password",
                ca_cert="auth_serv/ca.pem", phase2="auth=MSCHAPV2",
                expect_failure=True)

def test_eap_teap_eap_mschapv2_user_and_machine_fail_machine(dev, apdev):
    """EAP-TEAP with inner EAP-MSCHAPv2 using user and machine credentials (fail machine)"""
    check_eap_capa(dev[0], "TEAP")
    check_eap_capa(dev[0], "MSCHAPV2")
    params = int_teap_server_params(eap_teap_id="5")
    hapd = hostapd.add_ap(apdev[0], params)
    eap_connect(dev[0], hapd, "TEAP", "user", password="password",
                anonymous_identity="TEAP",
                machine_identity="machine",
                machine_password="wrong-machine-password",
                ca_cert="auth_serv/ca.pem", phase2="auth=MSCHAPV2",
                expect_failure=True)

def test_eap_teap_eap_mschapv2_user_and_machine_no_machine(dev, apdev):
    """EAP-TEAP with inner EAP-MSCHAPv2 using user and machine credentials (no machine)"""
    check_eap_capa(dev[0], "TEAP")
    check_eap_capa(dev[0], "MSCHAPV2")
    params = int_teap_server_params(eap_teap_id="5")
    hapd = hostapd.add_ap(apdev[0], params)
    eap_connect(dev[0], hapd, "TEAP", "user", password="password",
                anonymous_identity="TEAP",
                ca_cert="auth_serv/ca.pem", phase2="auth=MSCHAPV2",
                expect_failure=True)

def test_eap_teap_eap_mschapv2_user_and_eap_tls_machine(dev, apdev):
    """EAP-TEAP with inner EAP-MSCHAPv2 user and EAP-TLS machine credentials"""
    check_eap_capa(dev[0], "TEAP")
    check_eap_capa(dev[0], "MSCHAPV2")
    check_eap_capa(dev[0], "TLS")
    params = int_teap_server_params(eap_teap_id="5")
    hapd = hostapd.add_ap(apdev[0], params)
    eap_connect(dev[0], hapd, "TEAP", "user", password="password",
                anonymous_identity="TEAP",
                machine_identity="cert user",
                ca_cert="auth_serv/ca.pem", phase2="auth=MSCHAPV2",
                machine_phase2="auth=TLS",
                machine_ca_cert="auth_serv/ca.pem",
                machine_client_cert="auth_serv/user.pem",
                machine_private_key="auth_serv/user.key")

def test_eap_teap_fragmentation(dev, apdev):
    """EAP-TEAP with fragmentation"""
    check_eap_capa(dev[0], "TEAP")
    check_eap_capa(dev[0], "MSCHAPV2")
    params = hostapd.wpa2_eap_params(ssid="test-wpa2-eap")
    hapd = hostapd.add_ap(apdev[0], params)
    eap_connect(dev[0], hapd, "TEAP", "user",
                anonymous_identity="TEAP", password="password",
                ca_cert="auth_serv/ca.pem", phase2="auth=MSCHAPV2",
                fragment_size="100")

def test_eap_teap_tls_cs_sha1(dev, apdev):
    """EAP-TEAP with TLS cipher suite that uses SHA-1"""
    run_eap_teap_tls_cs(dev, apdev, "AES128-SHA")

def test_eap_teap_tls_cs_sha256(dev, apdev):
    """EAP-TEAP with TLS cipher suite that uses SHA-256"""
    run_eap_teap_tls_cs(dev, apdev, "AES128-SHA256")

def test_eap_teap_tls_cs_sha384(dev, apdev):
    """EAP-TEAP with TLS cipher suite that uses SHA-384"""
    run_eap_teap_tls_cs(dev, apdev, "AES256-GCM-SHA384")

def run_eap_teap_tls_cs(dev, apdev, cipher):
    check_eap_capa(dev[0], "TEAP")
    tls = dev[0].request("GET tls_library")
    if not tls.startswith("OpenSSL") and not tls.startswith("wolfSSL"):
        raise HwsimSkip("TLS library not supported for TLS CS configuration: " + tls)
    params = int_teap_server_params(eap_teap_auth="1")
    params['openssl_ciphers'] = cipher
    hapd = hostapd.add_ap(apdev[0], params)
    eap_connect(dev[0], hapd, "TEAP", "user",
                anonymous_identity="TEAP", password="password",
                ca_cert="auth_serv/ca.pem")

def wait_eap_proposed(dev, wait_trigger=None):
    ev = dev.wait_event(["CTRL-EVENT-EAP-PROPOSED-METHOD"], timeout=10)
    if ev is None:
        raise Exception("Timeout on EAP start")
    if wait_trigger:
        wait_fail_trigger(dev, wait_trigger)
    dev.request("REMOVE_NETWORK all")
    dev.wait_disconnected()
    dev.dump_monitor()

def test_eap_teap_errors(dev, apdev):
    """EAP-TEAP local errors"""
    check_eap_capa(dev[0], "TEAP")
    check_eap_capa(dev[0], "MSCHAPV2")
    params = hostapd.wpa2_eap_params(ssid="test-wpa2-eap")
    hapd = hostapd.add_ap(apdev[0], params)

    dev[0].connect("test-wpa2-eap", key_mgmt="WPA-EAP",
                   scan_freq="2412",
                   eap="TEAP", identity="user", password="password",
                   anonymous_identity="TEAP",
                   ca_cert="auth_serv/ca.pem", phase2="auth=MSCHAPV2",
                   wait_connect=False)
    wait_eap_proposed(dev[0])

    tests = [(1, "eap_teap_tlv_eap_payload"),
             (1, "eap_teap_process_eap_payload_tlv"),
             (1, "eap_teap_compound_mac"),
             (1, "eap_teap_tlv_result"),
             (1, "eap_peer_select_phase2_methods"),
             (1, "eap_peer_tls_ssl_init"),
             (1, "eap_teap_session_id"),
             (1, "wpabuf_alloc;=eap_teap_process_crypto_binding"),
             (1, "eap_peer_tls_encrypt"),
             (1, "eap_peer_tls_decrypt"),
             (1, "eap_teap_getKey"),
             (1, "eap_teap_session_id"),
             (1, "eap_teap_init")]
    for count, func in tests:
        with alloc_fail(dev[0], count, func):
            dev[0].connect("test-wpa2-eap", key_mgmt="WPA-EAP",
                           scan_freq="2412",
                           eap="TEAP", identity="user", password="password",
                           anonymous_identity="TEAP",
                           ca_cert="auth_serv/ca.pem", phase2="auth=MSCHAPV2",
                           wait_connect=False)
            wait_eap_proposed(dev[0], wait_trigger="GET_ALLOC_FAIL")

    tests = [(1, "eap_teap_derive_eap_msk"),
             (1, "eap_teap_derive_eap_emsk"),
             (1, "eap_teap_write_crypto_binding"),
             (1, "eap_teap_process_crypto_binding"),
             (1, "eap_teap_derive_msk;eap_teap_process_crypto_binding"),
             (1, "eap_teap_compound_mac;eap_teap_process_crypto_binding"),
             (1, "eap_teap_derive_imck")]
    for count, func in tests:
        with fail_test(dev[0], count, func):
            dev[0].connect("test-wpa2-eap", key_mgmt="WPA-EAP",
                           scan_freq="2412",
                           eap="TEAP", identity="user", password="password",
                           anonymous_identity="TEAP",
                           ca_cert="auth_serv/ca.pem", phase2="auth=MSCHAPV2",
                           wait_connect=False)
            wait_eap_proposed(dev[0], wait_trigger="GET_FAIL")

def test_eap_teap_errors2(dev, apdev):
    """EAP-TEAP local errors 2 (Basic-Password-Auth specific)"""
    check_eap_capa(dev[0], "TEAP")
    check_eap_capa(dev[0], "MSCHAPV2")
    params = int_teap_server_params(eap_teap_auth="1")
    hapd = hostapd.add_ap(apdev[0], params)

    tests = [(1, "eap_teap_process_basic_auth_req")]
    for count, func in tests:
        with alloc_fail(dev[0], count, func):
            dev[0].connect("test-wpa2-eap", key_mgmt="WPA-EAP",
                           scan_freq="2412",
                           eap="TEAP", identity="user", password="password",
                           anonymous_identity="TEAP",
                           ca_cert="auth_serv/ca.pem", phase2="auth=MSCHAPV2",
                           wait_connect=False)
            wait_eap_proposed(dev[0], wait_trigger="GET_ALLOC_FAIL")

    tests = [(1, "eap_teap_derive_imck")]
    for count, func in tests:
        with fail_test(dev[0], count, func):
            dev[0].connect("test-wpa2-eap", key_mgmt="WPA-EAP",
                           scan_freq="2412",
                           eap="TEAP", identity="user", password="password",
                           anonymous_identity="TEAP",
                           ca_cert="auth_serv/ca.pem", phase2="auth=MSCHAPV2",
                           wait_connect=False)
            wait_eap_proposed(dev[0], wait_trigger="GET_FAIL")

def test_eap_teap_eap_vendor(dev, apdev):
    """EAP-TEAP with inner EAP-vendor"""
    check_eap_capa(dev[0], "TEAP")
    check_eap_capa(dev[0], "VENDOR-TEST")
    params = hostapd.wpa2_eap_params(ssid="test-wpa2-eap")
    hapd = hostapd.add_ap(apdev[0], params)
    eap_connect(dev[0], hapd, "TEAP", "vendor-test-2",
                anonymous_identity="TEAP",
                ca_cert="auth_serv/ca.pem", phase2="auth=VENDOR-TEST")

def test_eap_teap_client_cert(dev, apdev):
    """EAP-TEAP with client certificate in Phase 1"""
    check_eap_capa(dev[0], "TEAP")
    params = int_teap_server_params(eap_teap_auth="2")
    hapd = hostapd.add_ap(apdev[0], params)

    # verify server accept a client with certificate, but no Phase 2
    # configuration
    eap_connect(dev[0], hapd, "TEAP", "user",
                anonymous_identity="TEAP",
                client_cert="auth_serv/user.pem",
                private_key="auth_serv/user.key",
                ca_cert="auth_serv/ca.pem")
    dev[0].dump_monitor()
    res = eap_reauth(dev[0], "TEAP")
    if res['tls_session_reused'] != '1':
        # This is not yet supported without PAC.
        logger.info("EAP-TEAP could not use session ticket")
        #raise Exception("EAP-TEAP could not use session ticket")

    # verify server accepts a client without certificate
    eap_connect(dev[1], hapd, "TEAP", "user",
                anonymous_identity="TEAP", password="password",
                ca_cert="auth_serv/ca.pem", phase2="auth=MSCHAPV2")
