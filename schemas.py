from pydantic import BaseModel, ConfigDict


# ---------- Shop ----------
class ShopCreate(BaseModel):
    slug: str
    name: str
    password: str


class ShopLogin(BaseModel):
    slug: str
    password: str


class ShopOut(BaseModel):
    id: int
    slug: str
    name: str

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    shop_slug: str
    shop_name: str


# ---------- Product ----------
class ProductCreate(BaseModel):
    name: str
    price: int = 0
    description: str = ""


class ProductOut(BaseModel):
    id: int
    name: str
    price: int
    description: str
    image_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


# ---------- FAQ ----------
class FaqOut(BaseModel):
    question: str
    answer: str

    model_config = ConfigDict(from_attributes=True)


class FaqGenerateRequest(BaseModel):
    product_name: str
    product_description: str = ""


# ---------- Chat ----------
class ChatRequest(BaseModel):
    message: str