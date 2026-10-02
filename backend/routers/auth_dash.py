from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from routers.auth import get_current_user
from models.users import Users
from models.contacts import Contacts, CountryContacts
from models.territories import Country

import os
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from jose import jwt, JWTError

from database import get_db
from models.users import Users
from models.contacts import Contacts, CountryContacts
from routers.auth import get_google_public_keys, IAP_AUDIENCE, get_current_user


def get_dashboard_access(request: Request, db: Session = Depends(get_db)):
    """
    Dedicated dependency for the Global Dashboard.
    It identifies the user strictly via the IAP header and checks if they
    are an internal team member or an external stakeholder.
    """
    iap_jwt = request.headers.get("X-Goog-IAP-JWT-Assertion")

    # Local development bypass (optional, remove if not needed)
    if not iap_jwt and os.environ.get("ENV") == "local":
        email = os.environ.get("MASTER_ADMIN_EMAIL").lower().strip()
    elif iap_jwt:
        try:
            unverified_header = jwt.get_unverified_header(iap_jwt)
            kid = unverified_header.get("kid")
            public_keys = get_google_public_keys()
            public_key = public_keys.get(kid)

            if not public_key:
                raise HTTPException(status_code=401, detail="Invalid IAP Token Header Key ID")

            payload = jwt.decode(
                iap_jwt,
                public_key,
                algorithms=["ES256"],
                audience=IAP_AUDIENCE
            )
            email = payload.get("email").lower().strip()

        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
    else:
        raise HTTPException(status_code=401, detail="Not authenticated. IAP Token required.")

    # 1. Internal Team Member? (Global Access)
    internal_user = db.query(Users).filter(func.lower(Users.email) == email).first()
    if internal_user:
        return {"is_global": True, "allowed_opcos": []}

    # 2. Stakeholder? (Market-Specific Access)
    stakeholder_opcos = (db.query(CountryContacts.country_id)  # Using ID to match RawAssets later
                         .join(Contacts, CountryContacts.contact_id == Contacts.id)
                         .filter(func.lower(Contacts.email) == email, CountryContacts.is_stakeholder == True)
                         .all())

    if stakeholder_opcos:
        allowed = [str(row[0]) for row in stakeholder_opcos if row[0]]
        return {"is_global": False, "allowed_opcos": allowed}

    # 3. Deny Access
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Dashboard access denied. You must be an internal team member or a designated OpCo stakeholder."
    )