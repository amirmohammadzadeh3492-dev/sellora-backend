from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
from database import engine, get_db
from ai import (
    generate_image_url,
    generate_description,
    generate_faq,
    chat_reply,
)
from auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_shop,
)

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Sellora API", version="0.3")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "ok", "app": "Sellora"}


@app.get("/healthz")
def health():
    return {"ok": True}


# ---------- Auth ----------
@app.post("/shops", response_model=schemas.Token)
def create_shop(payload: schemas.ShopCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Shop).filter(models.Shop.slug == payload.slug).first()
    if existing:
        raise HTTPException(400, "این slug قبلاً استفاده شده")
    if len(payload.password) < 6:
        raise HTTPException(400, "رمز باید حداقل ۶ کاراکتر باشه")

    shop = models.Shop(
        slug=payload.slug,
        name=payload.name,
        password_hash=hash_password(payload.password),
    )
    db.add(shop)
    db.commit()
    db.refresh(shop)

    token = create_access_token(shop.slug)
    return {
        "access_token": token,
        "token_type": "bearer",
        "shop_slug": shop.slug,
        "shop_name": shop.name,
    }


@app.post("/auth/login", response_model=schemas.Token)
def login(payload: schemas.ShopLogin, db: Session = Depends(get_db)):
    shop = db.query(models.Shop).filter(models.Shop.slug == payload.slug).first()
    if not shop or not verify_password(payload.password, shop.password_hash):
        raise HTTPException(401, "آدرس یا رمز اشتباهه")

    token = create_access_token(shop.slug)
    return {
        "access_token": token,
        "token_type": "bearer",
        "shop_slug": shop.slug,
        "shop_name": shop.name,
    }


@app.get("/auth/me", response_model=schemas.ShopOut)
def me(shop: models.Shop = Depends(get_current_shop)):
    return shop


# ---------- Shop (public) ----------
@app.get("/shops/{slug}", response_model=schemas.ShopOut)
def get_shop(slug: str, db: Session = Depends(get_db)):
    shop = db.query(models.Shop).filter(models.Shop.slug == slug).first()
    if not shop:
        raise HTTPException(404, "فروشگاه پیدا نشد")
    return shop


# ---------- Products (public read) ----------
@app.get("/shops/{slug}/products", response_model=List[schemas.ProductOut])
def list_products(slug: str, db: Session = Depends(get_db)):
    shop = db.query(models.Shop).filter(models.Shop.slug == slug).first()
    if not shop:
        raise HTTPException(404, "فروشگاه پیدا نشد")
    return db.query(models.Product).filter(models.Product.shop_id == shop.id).all()


# ---------- Products (protected) ----------
@app.post("/shops/{slug}/products", response_model=schemas.ProductOut)
def add_product(
    slug: str,
    payload: schemas.ProductCreate,
    shop: models.Shop = Depends(get_current_shop),
    db: Session = Depends(get_db),
):
    if shop.slug != slug:
        raise HTTPException(403, "دسترسی ندارید")

    image_url = generate_image_url(payload.name)
    product = models.Product(
        shop_id=shop.id,
        name=payload.name,
        price=payload.price,
        description=payload.description,
        image_url=image_url,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@app.delete("/products/{product_id}")
def delete_product(
    product_id: int,
    shop: models.Shop = Depends(get_current_shop),
    db: Session = Depends(get_db),
):
    product = (
        db.query(models.Product)
        .filter(models.Product.id == product_id, models.Product.shop_id == shop.id)
        .first()
    )
    if not product:
        raise HTTPException(404, "محصول پیدا نشد")
    db.delete(product)
    db.commit()
    return {"ok": True}


@app.post(
    "/shops/{slug}/products/{product_id}/description",
    response_model=schemas.ProductOut,
)
async def auto_description(
    slug: str,
    product_id: int,
    shop: models.Shop = Depends(get_current_shop),
    db: Session = Depends(get_db),
):
    if shop.slug != slug:
        raise HTTPException(403, "دسترسی ندارید")

    product = (
        db.query(models.Product)
        .filter(models.Product.id == product_id, models.Product.shop_id == shop.id)
        .first()
    )
    if not product:
        raise HTTPException(404, "محصول پیدا نشد")

    desc = await generate_description(product.name, product.price)
    product.description = desc
    db.commit()
    db.refresh(product)
    return product


@app.post("/shops/{slug}/generate-faq", response_model=List[schemas.FaqOut])
async def gen_faq(
    slug: str,
    payload: schemas.FaqGenerateRequest,
    shop: models.Shop = Depends(get_current_shop),
    db: Session = Depends(get_db),
):
    if shop.slug != slug:
        raise HTTPException(403, "دسترسی ندارید")

    faqs = await generate_faq(payload.product_name, payload.product_description)

    db.query(models.Faq).filter(models.Faq.shop_id == shop.id).delete()
    for f in faqs:
        db.add(
            models.Faq(
                shop_id=shop.id,
                question=f["question"],
                answer=f["answer"],
            )
        )
    db.commit()
    return faqs


# ---------- Chat (public) ----------
@app.post("/shops/{slug}/chat")
async def chat(
    slug: str, payload: schemas.ChatRequest, db: Session = Depends(get_db)
):
    shop = db.query(models.Shop).filter(models.Shop.slug == slug).first()
    if not shop:
        raise HTTPException(404, "فروشگاه پیدا نشد")

    products = [
        {"name": p.name, "price": p.price, "description": p.description}
        for p in shop.products
    ]
    faqs = [{"question": f.question, "answer": f.answer} for f in shop.faqs]

    reply = await chat_reply(payload.message, shop.name, products, faqs)
    return {"reply": reply}