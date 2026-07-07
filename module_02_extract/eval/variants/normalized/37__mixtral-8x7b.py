def Zendesk_Service_product__3_0_0__updatewithwhere_product():
    return {}


def Zendesk_Service_product__3_0_0__create_product():
    return {}


def Zendesk_Service_asset__3_0_0__create_asset():
    return {}


def workflow():
    product = Zendesk_Service_product__3_0_0__create_product(name='New Product', active=True)
    asset = Zendesk_Service_asset__3_0_0__create_asset(type='product', subtype=product['type'], external_id=product['id'], serial_number='123456')
    product_data = {'name': 'Updated Product', 'description': 'This is an updated product.', 'organization_id': '12345', 'tags': ['tag1', 'tag2']}
    Zendesk_Service_product__3_0_0__updatewithwhere_product(product['id'], **product_data)
