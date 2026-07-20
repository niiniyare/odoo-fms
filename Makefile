PYTHON := /home/niini/odoo18/.venv/bin/python3
ODOO   := $(PYTHON) /home/niini/odoo18/odoo-bin
CONF   := odoo.conf
DB     := shell_maanzoni_dev

.PHONY: run install upgrade shell test test-one reset

run:
	$(ODOO) -c $(CONF) -d $(DB) --dev=all

install:
	$(ODOO) -c $(CONF) -d $(DB) -i fms --stop-after-init

upgrade:
	$(ODOO) -c $(CONF) -d $(DB) -u fms --stop-after-init

shell:
	$(ODOO) -c $(CONF) -d $(DB) shell

test:
	$(ODOO) -c $(CONF) -d $(DB)_test -i fms --test-tags fms --stop-after-init

test-one:
	$(ODOO) -c $(CONF) -d $(DB)_test --test-tags /fms:$(T) --stop-after-init

reset:
	dropdb --if-exists $(DB) && createdb -O odoo $(DB) && $(MAKE) install
