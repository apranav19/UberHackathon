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
UBER_SANDBOX_API="https://sandbox-api.uber.com/v1/"

def create_user_object():
    """
        Creates a new User object and stores basic information in session
    """
    user_data = requests.get(
        BASE_UBER_API+'me',
        headers={
            'Authorization': 'Bearer {0}'.format(session[ACCESS_TOKEN_SESSION_ID]),
            'Content-Type': 'application/json'
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
    rides = []
    steps = []

    for c in candidate_pool:
        if c['id'] == candidate_id:
            candidate = c
            break

    company_airport, company_iata, company_position = fetch_airport_data(current_office['latitude'], current_office['longitude'])
    candidate_airport, candidate_iata, candidate_position = fetch_airport_data(candidate['latitude'], candidate['longitude'])

    rides.append({
        'ride_id': '1',
        'start_latitude': candidate['latitude'],
        'start_longitude': candidate['longitude'],
        'end_latitude': candidate_position[1],
        'end_longitude': candidate_position[0],
        'start_destination': candidate['address'],
        'end_destination' : candidate_airport
    })

    print('Ride Request 1 ------')
    rides_resp = make_ride_request(rides[0])
    rides[0]['status'] = rides_resp['status']
    rides[0]['driver'] = rides_resp['driver']
    rides[0]['eta'] = rides_resp['eta']

    dept_date = (datetime.strptime(candidate['interview_date'], '%m/%d/%Y %H:%M') - timedelta(days=1))
    ret_date = (datetime.strptime(candidate['interview_date'], '%m/%d/%Y %H:%M') + timedelta(days=1))

    steps.append({
        'type': 'Uber',
        'step_id': '1',
        'start_latitude': rides[0]['start_latitude'],
        'start_longitude': rides[0]['start_longitude'],
        'end_latitude': rides[0]['end_latitude'],
        'end_longitude': rides[0]['end_longitude'],
        'pickUpTime': (dept_date - timedelta(hours=2)).strftime("%I:%M %p"),
        'startDestination': rides[0]['start_destination'],
        'endDestination': rides[0]['end_destination'],
        'estimatedArrivalTime': '8:40 AM',
        'pickUpDate': str(dept_date.date()),
        'driverName': 'John'
    })

    # Make call to recommended flights
    f1, f2 = fetch_recommended_flight(candidate_iata, company_iata, dept_date.date(), ret_date.date())

    steps.append({
        'type': 'Flight',
        'step_id': '2',
        'flightTime': f1['departureTime'],
        'startDestination': candidate_airport,
        'endDestination': company_airport,
        'estimatedArrivalTime': f1['arrivalTime'],
        'airline': f1['airlineName'],
        'Gate': 'A22'
    })

    # Make call to recommended hotels
    hotel = fetch_recommended_hotels(current_office['latitude'], current_office['longitude'], dept_date, ret_date)

    rides.append({
        'ride_id': '2',
        'start_latitude': company_position[1],
        'start_longitude': company_position[0],
        'end_latitude': hotel['latitude'],
        'end_longitude': hotel['longitude']
    })

    print('Ride Request 2 ------')
    rides_resp = make_ride_request(rides[1])
    rides[1]['status'] = rides_resp['status']
    rides[1]['driver'] = rides_resp['driver']
    rides[1]['eta'] = rides_resp['eta']

    steps.append({
        'type': 'Hotel',
        'step_id': '3',
        'dayOfWeek': 'Friday',
        'checkInDate': hotel['check_in'],
        'checkOutDate': hotel['check_out'],
        'name': hotel['name']
    })

    steps.append({
        'type': 'Uber',
        'step_id': '4',
        'start_latitude': hotel['latitude'],
        'start_longitude': hotel['longitude'],
        'end_latitude': current_office['latitude'],
        'end_longitude': current_office['longitude'],
        'pickUpTime': (datetime.strptime(candidate['interview_date'], '%m/%d/%Y %H:%M') - timedelta(hours=2)).strftime("%I:%M %p"),
        'startDestination': hotel['address'],
        'endDestination': current_office['address'],
        'estimatedArrivalTime': '8:40 AM',
        'pickUpDate': str((datetime.strptime(candidate['interview_date'], '%m/%d/%Y %H:%M')).date()),
        'driverName': 'John'
    })

    rides.append({
        'ride_id': '3',
        'start_latitude': hotel['latitude'],
        'start_longitude': hotel['longitude'],
        'end_latitude': current_office['latitude'],
        'end_longitude': current_office['longitude']
    })

    print('Ride Request 3 ------')
    rides_resp = make_ride_request(rides[2])
    rides[2]['status'] = rides_resp['status']
    rides[2]['driver'] = rides_resp['driver']
    rides[2]['eta'] = rides_resp['eta']

    rides.append({
        'ride_id': '4',
        'end_latitude': hotel['latitude'],
        'end_longitude': hotel['longitude'],
        'start_latitude': current_office['latitude'],
        'start_longitude': current_office['longitude']
    })

    print('Ride Request 4 ------')
    rides_resp = make_ride_request(rides[3])
    rides[3]['status'] = rides_resp['status']
    rides[3]['driver'] = rides_resp['driver']
    rides[3]['eta'] = rides_resp['eta']

    rides.append({
        'ride_id': '5',
        'start_latitude': hotel['latitude'],
        'start_longitude': hotel['longitude'],
        'end_latitude': company_position[1],
        'end_longitude': company_position[0]
    })

    print('Ride Request 5 ------')
    rides_resp = make_ride_request(rides[4])
    rides[4]['status'] = rides_resp['status']
    rides[4]['driver'] = rides_resp['driver']
    rides[4]['eta'] = rides_resp['eta']

    rides.append({
        'ride_id': '6',
        'start_latitude': candidate_position[1],
        'start_longitude': candidate_position[0],
        'end_latitude': candidate['latitude'],
        'end_longitude': candidate['longitude']
    })

    print('Ride Request 6 ------')
    rides_resp = make_ride_request(rides[5])
    rides[5]['status'] = rides_resp['status']
    rides[5]['driver'] = rides_resp['driver']
    rides[5]['eta'] = rides_resp['eta']

    steps.append({
        'type': 'Uber',
        'step_id': '5',
        'end_latitude': hotel['latitude'],
        'end_longitude': hotel['longitude'],
        'start_latitude': current_office['latitude'],
        'start_longitude': current_office['longitude'],
        'pickUpTime': (datetime.strptime(candidate['interview_date'], '%m/%d/%Y %H:%M') + timedelta(hours=5)).strftime("%I:%M %p"),
        'startDestination': hotel['address'],
        'endDestination': current_office['address'],
        'pickUpDate': str((datetime.strptime(candidate['interview_date'], '%m/%d/%Y %H:%M')).date()),
        'estimatedArrivalTime': '8:40 AM',
        'driverName': 'John'
    })

    steps.append({
        'type': 'Uber',
        'step_id': '6',
        'end_latitude': hotel['latitude'],
        'end_longitude': hotel['longitude'],
        'start_latitude': current_office['latitude'],
        'start_longitude': current_office['longitude'],
        'pickUpTime': (ret_date - timedelta(hours=2)).strftime("%I:%M %p"),
        'endDestination': company_airport,
        'startDestination': hotel['address'],
        'pickUpDate': str((ret_date).date()),
        'estimatedArrivalTime': '8:40 AM',
        'driverName': 'John'
    })

    steps.append({
        'type': 'Flight',
        'step_id': '7',
        'flightTime': f2['departureTime'],
        'startDestination': company_airport,
        'endDestination': candidate_airport,
        'estimatedArrivalTime': f2['arrivalTime'],
        'airline': f2['airlineName'],
        'Gate': 'A22'
    })

    '''
        rides.append({
            'ride_id': '2',
            'start_latitude': company_position[1],
            'start_longitude': company_position[0],
            'end_latitude': hotel['latitude'],
            'end_longitude': hotel['longitude']
        })
    '''



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

    #res_inst = user_collection.insert_one(user_response)

    res_inst = user_collection.insert_one({'user_id': str(candidate_id), 'steps': steps})

    #session[session_key] = user_response


    return render_template('book.html', candidate=candidate, company_airport=company_airport,
            candidate_airport=candidate_airport, flight1=f1, flight2=f2, hotel=hotel,
            rides=rides,
            user=session.get('current_user', None))


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
    airport_position = resp_dict[0]['position']['coordinates']

    return airport_name, airport_iata, airport_position

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
        'check_out': str(checkout_date),
        'latitude': first_hotel_location['GeoLocation']['Latitude'],
        'longitude': first_hotel_location['GeoLocation']['Longitude']
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
        user_resp = {
            'steps': user_res['steps']
        }
        return jsonify(user_resp)

def make_ride_request(ride):
    if ACCESS_TOKEN_SESSION_ID in session:
        ride_resp = requests.post(
            UBER_SANDBOX_API+'requests',
            headers={
                'Authorization': 'bearer %s' % session['uber_at'],
                'Content-Type': 'application/json'
            },
            data=json.dumps({
                'start_latitude': ride['start_latitude'],
                'start_longitude': ride['start_longitude'],
                'end_latitude': ride['end_latitude'],
                'end_longitude': ride['end_longitude']
            })
        ).json()

        return ride_resp

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
