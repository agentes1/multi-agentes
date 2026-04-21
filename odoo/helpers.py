from enum import StrEnum

class Table(StrEnum):
    Product = 'product.product'
    Contact = 'res.partner'
    Ticket = 'helpdesk.ticket'
    TicketType = 'helpdesk.ticket.type'
    TicketTeam = 'helpdesk.ticket.team'
    TicketCategory = 'helpdesk.ticket.category'
    TicketStage = 'helpdesk.ticket.stage'
    TicketTag = 'helpdesk.ticket.tag'
    SaleOrder = 'sale.order'
    SaleOrderLine = 'sale.order.line'

contact_attrs = [
    "name",
    "is_company",
    "parent_id",        # links to company
    "email",
    "phone",
    "mobile",
    "vat",
    "street",
    "city",
    "zip",
    "country_id",
    "customer_rank",
    "supplier_rank",
    "property_payment_term_id"
]

product_attrs = [
    "name",
    "default_code",     # Internal Reference / SKU
    "barcode",
    "list_price",       # Sales Price
    "standard_price",   # Cost
    "type",             # storable, consumable, or service
    "qty_available",    # Stock on hand
    "uom_id",           # Unit of Measure
    "categ_id"          # Internal Category
]
