import django
django.setup()
import sys
from fgserver.atc.controllers import Requests, process_request

def process(instance):
    process_request(instance,instance)


if __name__ == "__main__":
    print(sys.argv)
    Requests.listen(process)
    print("Listening...")