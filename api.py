import requests
import json
import config

url = "https://api.tcpshield.com"
headers = {"X-API-KEY" : config.api_key}

def get_network_id(network_name: str):
    data = json.loads(requests.get(f"{url}/networks", headers=headers).text)
    network_id = None
    for i in data:
        if i["name"] == network_name:
            network_id = i["id"]
            break
    return network_id

def get_domains(network_name: str):
    network_id = get_network_id(network_name)
    if network_id == None:
        return None
    else:
        return json.loads(requests.get(f"{url}/networks/{network_id}/domains", headers=headers).text)
    
def get_domain_id(network_name: str, domain: str):
    domains = get_domains(network_name)
    domain_id = None
    for i in domains:
        if i["name"] == domain:
            domain_id = i["id"]
            break
    if domain_id == None:
        return None
    else:
        return domain_id
    
def delete_domain(network_name: str, domain: str):
    network_id = get_network_id(network_name)
    domain_id = get_domain_id(network_name, domain)
    if network_id is None or domain_id is None:
        return 404
    return requests.delete(f"{url}/networks/{network_id}/domains/{domain_id}", headers=headers).status_code

def get_backend_id(network_name: str, backend_name: str):
    network_id = get_network_id(network_name)
    data = json.loads(requests.get(f"{url}/networks/{network_id}/backendSets", headers=headers).text)
    backend_id = None
    for i in data:
        if i["name"] == backend_name:
            backend_id = i["id"]
    return backend_id

def create_domain(network_name: str, domain: str, backend_name: str):
    network_id = get_network_id(network_name)
    backend_id = get_backend_id(network_name, backend_name)
    data = {"name": domain, "backend_set_id": backend_id, "bac": False}
    response = requests.post(f"{url}/networks/{network_id}/domains", headers=headers, json=data)
    return response.status_code

def delete_backend(network_name: str, backend_name: str):
    network_id = get_network_id(network_name)
    backend_id = get_backend_id(network_name, backend_name)
    response = requests.delete(f"{url}/networks/{network_id}/backendSets/{backend_id}", headers=headers)
    return response.status_code

def create_backend(network_name: str, backend_name: str, hostname: str, port: int, proxyprotocol: bool):
    network_id = get_network_id(network_name)
    body = {"name": backend_name, "backends": [f'{hostname}:{port}'], "proxy_protocol": proxyprotocol, "vulcan_ac_enabled": False, "load_balancing_mode": 0}
    response = requests.post(f"{url}/networks/{network_id}/backendSets", headers=headers, json=body)
    return response.status_code

def verify_domain(network_name: str, domain:str):
    network_id = get_network_id(network_name)
    domain_id = get_domain_id(network_name, domain)
    response = requests.get(f"{url}/networks/{network_id}/domains/{domain_id}/verify", headers=headers)
    return response.status_code # 200 - 정상 / 403: 인증 실패