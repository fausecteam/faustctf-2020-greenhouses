DESTDIR ?= dist_root

build:
	echo ok

install:
	cp -r -d etc $(DESTDIR)/
	install -D -m 755 -t $(DESTDIR)/opt/bin/ register.sh


.PHONY: install build all
