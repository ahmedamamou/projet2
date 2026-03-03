# Makefile for smart farm Contiki-NG firmware
# Usage: make TARGET=cooja [sensor_node|border_router]

CONTIKI_PROJECT = sensor_node border_router
all: $(CONTIKI_PROJECT)

CONTIKI ?= $(HOME)/contiki-ng

# Enable modules
MODULES += os/net/app-layer/mqtt
MODULES += os/services/energest

# Compiler flags
CFLAGS += -DPROJECT_CONF_H=\"project-conf.h\"

include $(CONTIKI)/Makefile.include
