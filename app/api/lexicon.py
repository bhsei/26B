from fastapi import APIRouter, Query
from sqlalchemy.orm import sessionmaker

def create_lexicon_router(sessions: sessionmaker) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["lexicon"])

    contexts_db = [
        {
            "keywords": ["café", "cafe", "coffee", "drink", "water"],
            "tiles": [
                {"name": "Water", "image": "/static/symbols/water.png", "description": "Request water or a beverage."},
                {"name": "Coffee", "image": "/static/symbols/coffee.png", "description": "Request a coffee or visit a café."},
                {"name": "Sugar", "image": "/static/symbols/sugar.png", "description": "Add sugar to your beverage or food."},
                {"name": "Milk", "image": "/static/symbols/milk.png", "description": "Request milk / Add milk to your beverage."},
                {"name": "Hot", "image": "/static/symbols/hot.png", "description": "Specify a hot drink or meal."},
                {"name": "Cold", "image": "/static/symbols/cold.png", "description": "Specify a cold drink or meal."},
                {"name": "Take away", "image": "/static/symbols/takeaway.png", "description": "Indicate an order to go."},
                {"name": "Eat in", "image": "/static/symbols/eatin.png", "description": "Indicate consuming on-site."}
            ]
        },
        {
            "keywords": ["post office", "poste", "mail", "package", "letter", "ship"],
            "tiles": [
                {"name": "Parcel", "image": "/static/symbols/parcel.png", "description": "Send or track packages."},
                {"name": "Letter", "image": "/static/symbols/letter.png", "description": "Mail letters or documents."},
                {"name": "Retrieve", "image": "/static/symbols/retreive.png", "description": "Pick up mail or packages."},
                {"name": "Deliver", "image": "/static/symbols/deliver.png", "description": "Deliver mail or packages. / Adress delivery issue."}
            ]
        },
        {
            "keywords": ["restaurant", "resto", "diner", "lunch", "eat", "breakfast", "brunch", "bill", "pay"],
            "tiles": [
                {"name": "Order", "image": "/static/symbols/order.png", "description": "Place food or drink orders."},
                {"name": "Bill", "image": "/static/symbols/bill.png", "description": "Request the bill."},
                {"name": "Pay", "image": "/static/symbols/pay.png", "description": "Handle payment."},
                {"name": "Menus", "image": "/static/symbols/menu.png", "description": "Ask for menus."},
                {"name": "Reservation", "image": "/static/symbols/reservation.png", "description": "Adress reservations."},
                {"name": "Drinks", "image": "/static/symbols/drinks.png", "description": "View or order drinks."},
                {"name": "Main courses", "image": "/static/symbols/maincourses.png", "description": "Select main dishes."}
            ]
        },
        {
            "keywords": ["street", "outside", "direction", "location", "way", "subway", "bus", "find", "information", "hospital", "city center"],
            "tiles": [
                {"name": "Subway station", "image": "/static/symbols/subway.png", "description": "Locate or discuss the subway."},
                {"name": "Bus stop", "image": "/static/symbols/bus.png", "description": "Locate or discuss bus transport navigation."},
                {"name": "Police station", "image": "/static/symbols/police.png", "description": "Find assistance or police. / Alert the police."},
                {"name": "Information center", "image": "/static/symbols/infocenter.png", "description": "Seek tourist or local information. / Locate information center"},
                {"name": "City center", "image": "/static/symbols/citycenter.png", "description": "Navigate toward downtown."},
                {"name": "Hospital", "image": "/static/symbols/hospital.png", "description": "Locate medical help. / Ask for medical help."}
            ]
        },
        {
            "keywords": ["clothes", "shopping", "mall", "store", "outlet", "size", "shoes", "snickers", "price", "pricetag"],
            "tiles": [
                {"name": "Item", "image": "/static/symbols/item.png", "description": "Refer to a specific product or article."},
                {"name": "Size +", "image": "/static/symbols/sizeup.png", "description": "Ask for a larger size."},
                {"name": "Size -", "image": "/static/symbols/sizedown.png", "description": "Ask for a smaller size."},
                {"name": "Pricetag", "image": "/static/symbols/pricetag.png", "description": "Check prices of a certain item."},
                {"name": "Color", "image": "/static/symbols/color.png", "description": "Discuss product color options."}
            ]
        }
    ]

    @router.get("/lexicon")
    def get_lexicon(query: str | None = Query(None)):
        query_str = (query or "").lower()
        
        for context in contexts_db:
            if any(kw in query_str for kw in context["keywords"]):
                return context["tiles"]
        
        return contexts_db[0]["tiles"]

    return router