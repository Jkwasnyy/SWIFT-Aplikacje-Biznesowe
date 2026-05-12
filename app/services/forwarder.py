import requests

def forward_message(url, xml, headers=None, timeout=3.0):
    request_headers = {"Content-Type": "application/xml"}
    if headers:
        request_headers.update(headers)

    try:
        response = requests.post(
            url,
            data=xml,
            headers=request_headers,
            timeout=timeout,
        )
        return response.status_code, response.text
    except requests.RequestException as exc:
        raise RuntimeError(f"Forwarding failed: {exc}") from exc