def Microsoft_Entra_ID_Devices__4_0_0__retrievewithwhere_Devices(devices_isCompliant_0: bool = None, devices_isCompliant_1: bool = None):
    return [{"isCompliant": devices_isCompliant_0}, {"isCompliant": devices_isCompliant_1}]


def Microsoft_Exchange_Messages__2_0_0__SENDOUTLOOK_Messages():
    return {}


def workflow(devices_isCompliant_0: bool, devices_isCompliant_1: bool):
    if not devices_isCompliant_0 and (not devices_isCompliant_1):
        Microsoft_Exchange_Messages__2_0_0__SENDOUTLOOK_Messages()
    return None
