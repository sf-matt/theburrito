from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/validate', methods=['POST'])
def validate():
    request_info = request.get_json()
    pod_name = request_info['request']['object']['metadata']['name']
    uid = request_info['request']['uid']

    if 'badpod' in pod_name:
        response = {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "response": {
                "uid": uid,
                "allowed": False,
                "status": {
                    "message": f"Pod name '{pod_name}' is not allowed."
                }
            }
        }
    else:
        response = {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "response": {
                "uid": uid,
                "allowed": True
            }
        }

    return jsonify(response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=443, ssl_context=('/app/certs/cert.pem', '/app/certs/key.pem'))