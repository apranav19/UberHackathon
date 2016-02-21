from flask import Flask, render_template
import requests
import UserFactory
from datetime import datetime, timedelta

app = Flask(__name__)

candidate_pool = UserFactory.generate_candidates(5)

current_office = {
   'company_name': 'Blue Whale Inc.',
   'address': '1501 Magnolia Ave, San Bruno, CA 94066',
   'latitude': '37.6089039',
   'longitude': '-122.4041261'
}

EXPEDIA_API_KEY="CCK2GO59nPAFwiFiPX4D3HsZORoHWat7"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/candidates')
def get_candidates():
    return render_template('pool.html', candidates=candidate_pool, company=current_office)

@app.route('/login')
def test():
    return 'Hello World'

@app.route('/book/<int:candidate_id>')
def book_candidate(candidate_id):
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
        'address': first_hotel_location['StreetAddress'] + ',' + first_hotel_location['City'] + ',' + first_hotel_location['Province']
    }

    return hotel


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
