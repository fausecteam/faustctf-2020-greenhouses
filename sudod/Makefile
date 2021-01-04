DESTDIR ?=

all:
	@echo nothing to compile, just install it

install:
	install -D -m 755 -t $(DESTDIR)/opt/bin/ sudod.py
	install -D -m 755 -t $(DESTDIR)/opt/bin/ sudoc.py
	install -D -m 644 -t $(DESTDIR)/etc/dbus-1/system.d/ net.faustctf.SuDoD.conf 
	install -D -m 644 -t $(DESTDIR)/etc/polkit-1/rules.d/ sudoers.rules
	install -D -m 644 -t $(DESTDIR)/usr/share/polkit-1/actions net.faustctf.SuDoD.policy
	install -D -m 644 -t $(DESTDIR)/etc/dbus-1/system-services/ net.faustctf.SuDoD.service
	install -D -m 644 -t $(DESTDIR)/etc/systemd/system/ sudod.service

uninstall:
	rm -f /opt/bin/sudod.py /opt/bin/sudoc.py /etc/dbus-1/system.d/net.faustctf.SuDoD.conf

.PHONY: install uninstall all
