# ESP32-S2 flashing helpers. Put the board in download mode first:
# hold BOOT, tap RESET, release BOOT. Unplug/replug after flashing.

PORT ?= /dev/cu.usbmodem01
CHIP ?= esp32s2
BOARD ?= esp32-s2
VENV ?= .venv
IMAGE ?= $(firstword $(wildcard webusb/*-$(CHIP)-gh*.bin))
BACKUP ?= backups/$(CHIP)-$(shell date +%Y%m%d-%H%M%S).bin

# no-reset: the S2 native USB port drops on esptool's auto reset
ESPTOOL = $(VENV)/bin/esptool --chip $(CHIP) --port $(PORT) --before no-reset --after no-reset

.PHONY: help venv info flash backup erase repack web

help: ## list targets
	@grep -E '^[a-z]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-7s %s\n", $$1, $$2}'
	@echo "  image   $(IMAGE)"

$(VENV)/bin/esptool:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -q esptool==5.5.0 littlefs-python==0.19.0

venv: $(VENV)/bin/esptool ## create .venv with esptool and littlefs-python

info: venv ## show chip and flash info
	$(ESPTOOL) flash-id

flash: venv ## write IMAGE (default: this branch's GoldHEN image)
	$(ESPTOOL) write-flash 0x0 $(IMAGE)

backup: venv ## save the full 4MB flash to BACKUP (restore: make flash IMAGE=<file>)
	mkdir -p $(dir $(BACKUP))
	$(ESPTOOL) read-flash 0x0 0x400000 $(BACKUP)

erase: venv ## erase the whole flash
	$(ESPTOOL) erase-flash

repack: venv ## rebuild images: make repack GOLDHEN=<goldhen.bin> LABEL=<version>
	@test -n "$(GOLDHEN)" -a -n "$(LABEL)" || { echo "usage: make repack GOLDHEN=<goldhen.bin> LABEL=<version>"; exit 1; }
	$(VENV)/bin/python scripts/goldhen-repack.py $(GOLDHEN) $(LABEL) $(BOARD)

web: ## serve the stock web installer at http://localhost:8000
	cd webusb && python3 -m http.server 8000
