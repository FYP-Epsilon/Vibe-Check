def Zendesk_Service_product__3_0_0__updatewithwhere_product():
    return {}


def Zendesk_Service_product__3_0_0__create_product():
    return {}


def Zendesk_Service_asset__3_0_0__create_asset():
    return {}


def workflow():
    product_id = Zendesk_Service_product__3_0_0__create_product()
    asset_id = Zendesk_Service_asset__3_0_0__create_asset()
    Zendesk_Service_product__3_0_0__updatewithwhere_product(product_id, asset_id)
