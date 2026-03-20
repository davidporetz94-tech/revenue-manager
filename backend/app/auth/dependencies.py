"""Auth dependencies — JWT token verification and user extraction."""
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User

security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Extract and verify user from JWT token.

    Falls back to demo user only when DEMO_MODE is enabled.
    """
    if credentials is None:
        if settings.DEMO_MODE:
            user = db.query(User).filter_by(email="demo@example.com").first()
            if user:
                return user
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter_by(id=user_id, is_active=True).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


def verify_property_access(db: Session, property_id: str, user: User):
    """Verify that a property belongs to the user's organization.

    Args:
        db: database session.
        property_id: UUID of the property.
        user: authenticated user.

    Returns:
        Property ORM object if access is allowed.

    Raises:
        HTTPException 404 if property not found or not in user's org.
    """
    from app.models.property import Property

    prop = db.query(Property).filter_by(
        id=property_id, organization_id=user.organization_id
    ).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop
