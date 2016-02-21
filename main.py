from flask import Flask, render_template
import requests
import UserFactory

app = Flask(__name__)

candidate_pool = UserFactory.generate_candidates(5)

current_office = {
   'company_name': 'Blue Whale Inc.',
   'address': '144 Townsend St, San Francisco, CA 94107'
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

    params = {
        'apikey': EXPEDIA_API_KEY,
        'lat': c['latitude'],
        'lng': c['longitude'],
        'type': 'airport',
        'verbose': 3,
        'within': '50km'

    }
    resp = requests.get('http://terminal2.expedia.com/x/geo/features?', params=params)
    resp_dict = resp.json()
    airport_name = resp_dict[0]['name']

    return render_template('book.html', candidate=candidate, airport=airport_name)


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
