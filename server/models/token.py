from typing import Optional

from pydantic import BaseModel


class Token(BaseModel):
    """
    Pydantic model for the response when a user logs in.
    This is what the client (frontend) will receive.
    """

    access_token: str
    token_type: str


class TokenData(BaseModel):
    """
    Pydantic model for the data we encode inside the JWT.
    We'll store the username and user_id for easy identification.
    """

    username: Optional[str] = None
    user_id: Optional[int] = None
