ALL=pasn-init
include ../rules.include

CFLAGS += -DCONFIG_PASN
CFLAGS += -DCONFIG_SAE
CFLAGS += -DCONFIG_SHA256
CFLAGS += -DCONFIG_SHA384
CFLAGS += -DCONFIG_ECC
CFLAGS += -DCONFIG_FILS
CFLAGS += -DCONFIG_IEEE80211R
CFLAGS += -DCONFIG_PTKSA_CACHE

OBJS += $(SRC)/utils/common.o
OBJS += $(SRC)/utils/os_unix.o
OBJS += $(SRC)/utils/wpa_debug.o
OBJS += $(SRC)/utils/wpabuf.o
OBJS += $(SRC)/common/sae.o
OBJS += $(SRC)/common/dragonfly.o
OBJS += $(SRC)/common/wpa_common.o
OBJS += $(SRC)/common/ieee802_11_common.o
OBJS += $(SRC)/crypto/crypto_openssl.o
OBJS += $(SRC)/crypto/dh_groups.o
OBJS += $(SRC)/crypto/sha1-prf.o
OBJS += $(SRC)/crypto/sha256-prf.o
OBJS += $(SRC)/crypto/sha384-prf.o
OBJS += $(SRC)/crypto/sha256-kdf.o
OBJS += $(SRC)/crypto/sha384-kdf.o
OBJS += $(SRC)/rsn_supp/wpa_ie.o
OBJS += $(SRC)/rsn_supp/pmksa_cache.o
OBJS += $(SRC)/pasn/pasn_common.o
OBJS += $(SRC)/pasn/pasn_initiator.o

OBJS += pasn-init.o

_OBJS_VAR := OBJS
include ../../../src/objs.mk

pasn-init: $(OBJS)
	$(LDO) $(LDFLAGS) -o $@ $^ -lcrypto

clean: common-clean
	rm -f pasn-init *~ *.o *.d ../*~ ../*.o ../*.d
