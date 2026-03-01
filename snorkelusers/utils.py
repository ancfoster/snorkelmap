from ipware import get_client_ip
import geoip2.database
import os
from dotenv import load_dotenv

def get_country_code_from_ip(request):
    """
    Use MindMachine's GeoLite2 database to get the county code of a new user uisng their IP address
    """
    ip, _ = get_client_ip(request)
    if (os.environ.get('environment') == 'development'):
        ip = '90.242.222.105'
    if ip:
        try:
            reader = geoip2.database.Reader('data/GeoLite2-Country.mmdb')
            response = reader.country(ip)
            return response.country.iso_code
        except Exception:
            return None
    return None