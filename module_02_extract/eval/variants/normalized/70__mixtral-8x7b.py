def Coupa_suppliers__4_0_0__create_suppliers():
    return {}


def Coupa_remit_to_addresses__4_0_0__create_remit_to_addresses():
    return {}


def workflow():
    supplier = Coupa_suppliers__4_0_0__create_suppliers()
    remit_to_address = {'name': 'Remit To Address', 'address_line1': '123 Main St', 'city': 'Mountain View', 'region': 'CA', 'country': 'US', 'zip_code': '94043'}
    created_remit_to_address = Coupa_remit_to_addresses__4_0_0__create_remit_to_addresses(remit_to_address)
    supplier['remit_to_address_id'] = created_remit_to_address['id']
    updated_supplier = Coupa_suppliers__4_0_0__create_suppliers(supplier)
    return updated_supplier
