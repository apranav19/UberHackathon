#from faker import Factory

def generate_candidates(num_candidates):
    #fake_factory = Factory.create('en_US')
    #candidate_pool = [{'name': fake_factory.name(), 'address': fake_factory.address()} for candidate_num in range(num_candidates)]
    candidate_pool = [
        {
            'id': 1,
            'name': 'Tom Jones',
            'address': '17620 International Blvd, Seattle, WA 98188',
            'interview_date': '03/22/2016 13:00',
            'latitude': '47.4417966',
            'longitude': '-122.3050032'
        },
        {
            'id': 2,
            'name': 'Jane Doe',
            'address': '1844 SW Morrison St, Portland, OR 97205',
            'interview_date': '04/12/2016 13:00',
            'latitude': '45.5216743',
            'longitude': '-122.6930176'
        },
        {
            'id': 3,
            'name': 'Philip Thompson',
            'address': '4800 El Camino Real, Los Altos, CA 94022',
            'interview_date': '04/22/2016 13:00',
            'latitude': '37.3970128',
            'longitude': '-122.1072098'
        }
    ]

    return candidate_pool
