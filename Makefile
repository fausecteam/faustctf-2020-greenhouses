SERVICE := greenhouses
DESTDIR ?= dist_root
SERVICEDIR ?= /srv/$(SERVICE)

CONTAINER = $(shell realpath $(DESTDIR)$(SERVICEDIR)/container)

.PHONY: build install clean

build:
	$(MAKE) -C sudod

$(DESTDIR)$(SERVICEDIR):
	mkdir -p $@

install: build $(DESTDIR)$(SERVICEDIR)
	mkdir -p $(DESTDIR)$(SERVICEDIR)
	cp -a --no-preserve=ownership,timestamps container_template $(CONTAINER)
	make -C sudod install DESTDIR=$(CONTAINER)
	make -C gate install DESTDIR=$(CONTAINER)
	make -C greenhoused install DESTDIR=$(CONTAINER)
	mkdir -p $(DESTDIR)/var/lib/machines/
	ln -s ../../../srv/$(SERVICE)/container $(DESTDIR)/var/lib/machines/$(SERVICE)
	cp -a --no-preserve=ownership,timestamps etc $(DESTDIR)/
	# something creates 777-files in ci, quickfix:
	chmod -R g-w,o-w dist_root

clean:
	rm -r dist_root

