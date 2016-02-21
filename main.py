from flask import Flask, render_template, jsonify, session, redirect, request, url_for
import requests
import UserFactory
from datetime import datetime, timedelta
from rauth import OAuth2Service
import sys
from pymongo import MongoClient
from bson.json_util import dumps
import json

app = Flask(__name__)
app.config.from_object('app_config')
app.secret_key = app.config['APP_SECRET']

candidate_pool = UserFactory.generate_candidates(5)
client = MongoClient('mongodb://foradmin:fora@ds035240.mongolab.com:35240/foradb')
foradb = client['foradb']
user_collection = foradb['userdata']

current_office = {
   'company_name': 'Blue Whale Inc.',
   'address': '1501 Magnolia Ave, San Bruno, CA 94066',
   'latitude': '37.6089039',
   'longitude': '-122.4041261'
}

EXPEDIA_API_KEY="CCK2GO59nPAFwiFiPX4D3HsZORoHWat7"
UBER_CLIENT_ID="P7I1oMD8sDWl3kfyrcfPUv-mlzzAehMF"
UBER_CLIENT_SEC="vfD2BAJLdAxD-i3IlyLbFSawsZE4S79XgFvybzTv"
ACCESS_TOKEN_SESSION_ID = 'uber_at'
BASE_UBER_API="https://api.uber.com/v1/"
UBER_SANDBOX_API="https://sandbox-api.uber.com/v1"

def create_user_object():
    """
        Creates a new User object and stores basic information in session
    """
    user_data = requests.get(
        BASE_UBER_API+'me',
        headers={
            'Authorization': 'Bearer {0}'.format(session[ACCESS_TOKEN_SESSION_ID])
        }
    ).json()
    session['current_user'] = user_data

def create_uber_auth():
    """
        Returns an OAuth2Service object that contains the required credentials
    """
    uber_obj = OAuth2Service(
        client_id=UBER_CLIENT_ID,
        client_secret=UBER_CLIENT_SEC,
        name='TestApp1Prv',
        authorize_url='https://login.uber.com/oauth/authorize',
        access_token_url='https://login.uber.com/oauth/token',
        base_url='https://api.uber.com/v1/'
    )

    uber_params = {
        'response_type': 'code',
        'redirect_uri': app.config['REDIRECT_URI'],
        'scope': 'profile request',
    }

    return uber_obj.get_authorize_url(**uber_params)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/candidates')
def get_candidates():
    current_user = None
    if ACCESS_TOKEN_SESSION_ID in session:
        create_user_object()
    return render_template('pool.html', candidates=candidate_pool, company=current_office, user=session.get('current_user', None))

@app.route('/login')
def test():
    uber_auth_url = create_uber_auth()
    return redirect(uber_auth_url)

@app.route('/callback')
def login_redirect():
    parameters = {
        'redirect_uri': app.config['REDIRECT_URI'],
        'code': request.args.get('code', None),
        'grant_type': 'authorization_code',
    }

    response = requests.post(
        'https://login.uber.com/oauth/token',
        auth=(
            UBER_CLIENT_ID,
            UBER_CLIENT_SEC,
        ),
        data=parameters,
    )

    access_token = response.json().get('access_token')
    if access_token:
        session[ACCESS_TOKEN_SESSION_ID] = access_token
    return redirect(url_for('get_candidates'))

@app.route('/book/<int:candidate_id>')
def book_candidate(candidate_id):
    session_key = 'user'+str(candidate_id)
    candidate = None

    for c in candidate_pool:
        if c['id'] == candidate_id:
            candidate = c
            break

    company_airport, company_iata = fetch_airport_data(current_office['latitude'], current_office['longitude'])
    candidate_airport, candidate_iata = fetch_airport_data(candidate['latitude'], candidate['longitude'])

    dept_date = (datetime.strptime(candidate['interview_date'], '%m/%d/%Y %H:%M') - timedelta(days=1)).date()
    ret_date = (datetime.strptime(candidate['interview_date'], '%m/%d/%Y %H:%M') + timedelta(days=1)).date()

    # Make call to recommended flights
    f1, f2 = fetch_recommended_flight(candidate_iata, company_iata, dept_date, ret_date)

    # Make call to recommended hotels
    hotel = fetch_recommended_hotels(current_office['latitude'], current_office['longitude'], dept_date, ret_date)

    user_response = {
        'user_id': str(candidate_id),
        'name': candidate['name'],
        'interview_date': candidate['interview_date'],
        'address': candidate['address'],
        'hotel': hotel,
        'planes': [
            {
                'origin': candidate_airport,
                'destination': company_airport,
                'departure': str(f1['departureTime']),
                'arrival': str(f1['arrivalTime']),
                'flight_number': f1['airlineCode'] + "-" + f1['flightNumber']
            },
            {
                'origin': company_airport,
                'destination': candidate_airport,
                'departure': str(f2['departureTime']),
                'arrival': str(f2['arrivalTime']),
                'flight_number': f2['airlineCode'] + "-" + f2['flightNumber']
            }
        ]
    }

    res_inst = user_collection.insert_one(user_response)

    #session[session_key] = user_response


    return render_template('book.html', candidate=candidate, company_airport=company_airport, candidate_airport=candidate_airport, flight1=f1, flight2=f2, hotel=hotel)


def fetch_airport_data(lat, lng):
    params = {
        'apikey': EXPEDIA_API_KEY,
        'lat': lat,
        'lng': lng,
        'type': 'airport',
        'verbose': 3,
        'within': '20km'
    }

    resp = requests.get('http://terminal2.expedia.com/x/geo/features?', params=params)
    resp_dict = resp.json()

    airport_name = resp_dict[0]['name']
    airport_iata = resp_dict[0]['tags']['iata']['airportCode']['value']

    return airport_name, airport_iata

def fetch_recommended_flight(origin, destination, dept_date, ret_date):
    params = {
        'apikey': EXPEDIA_API_KEY,
        'departureAirport': origin,
        'arrivalAirport': destination,
        'departureDate': dept_date,
        'returnDate': ret_date
    }

    resp = requests.get('http://terminal2.expedia.com/x/mflights/search?', params=params)
    resp_dict = resp.json()

    rec_first_flight = resp_dict['legs'][0]['segments'][0]
    rec_sec_flight = resp_dict['legs'][1]['segments'][0]

    return rec_first_flight, rec_sec_flight

def fetch_recommended_hotels(lat, lng, checkin_date, checkout_date):
    params = {
        'apikey': EXPEDIA_API_KEY,
        'location': lat+','+lng,
        'dates': str(checkin_date)+','+str(checkout_date),
        'radius': '5km'
    }

    resp = requests.get('http://terminal2.expedia.com/x/hotels?', params=params)
    resp_dict =resp.json()
    first_hotel = resp_dict['HotelInfoList']['HotelInfo'][0]
    first_hotel_location = first_hotel['Location']

    hotel = {
        'name': first_hotel['Name'],
        'address': first_hotel_location['StreetAddress'] + ',' + first_hotel_location['City'] + ',' + first_hotel_location['Province'],
        'check_in': str(checkin_date),
        'check_out': str(checkout_date)
    }

    return hotel

@app.route('/candidate/<int:candidate_id>.json')
def fetch_candidate(candidate_id):
    user_res = user_collection.find_one({'user_id': str(candidate_id)})
    if user_res is None:
        return jsonify({
            'error': 'Candidate ID not found'
        })
    else:
        user_response = {
            'user_id': str(user_res['user_id']),
            'name': user_res['name'],
            'interview_date': user_res['interview_date'],
            'address': user_res['address'],
            'hotel': user_res['hotel'],
            'planes': user_res['planes']
        }
        return jsonify(user_response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
