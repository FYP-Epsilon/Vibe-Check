def Microsoft_Exchange_Events__2_0_0__deletewithwhere_Events():
    return {}


def workflow():
    meeting = {'Subject': 'Meeting to cancel', 'IsOrganizer': True}
    Microsoft_Exchange_Events__2_0_0__deletewithwhere_Events(Meeting=meeting, Filter="Startswith(Subject,'Meeting to cancel')")
