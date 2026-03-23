from ninja import Schema

class UsernameCheckResponse(Schema):
    username: str
    available: bool