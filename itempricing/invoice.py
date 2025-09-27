from erpnext.stock.doctype.batch.batch import get_batch_no, get_batch_qty, set_batch_nos
from mtolori_api.utils import *
from frappe.utils import flt
from frappe.utils import flt, cint, getdate, get_datetime, nowdate, nowtime, add_days, unique, month_diff
import traceback
from erpnext import get_default_company


def get_main_company():
    return frappe.get_doc("Company", get_default_company())

@frappe.whitelist(allow_guest=True)  
def create(**args):
    try:
        sales_invoice_doc = frappe.db.get_value('Sales Invoice', {'custom_order_id': str(args.get('order_id'))}, ['name'], as_dict=1) 
        if not sales_invoice_doc:
            
            sales_invoice_doc = frappe.new_doc('Sales Invoice')
            company = get_main_company()
            customer = 'Walk-in Customer'
            sales_invoice_doc.discount_amount = 0
            sales_invoice_doc.customer = customer
            sales_invoice_doc.due_date = frappe.utils.data.today()
            sales_invoice_doc.debit_to = company.default_receivable_account
            sales_invoice_doc.custom_order_id = str(args.get('order_id'))
            sales_invoice_doc.update_stock = 0
            
            total_amount = 0
            
            for itm in args.get('items'):
                item = get_or_create_item(itm.get('item_name'))
                default_income_account = company.default_income_account
                for item_default in item.item_defaults:
                    if item_default.company == company.name:
                        if item_default.income_account:
                            default_income_account = item_default.income_account
                           
                amount = flt(itm.get('rate')) * flt(itm.get('quantity'))
                sales_invoice_doc.append('items',{
                    'item_code': item.item_code,
                    'item_name': item.item_name,
                    'description': item.description,
                    'qty': itm.get('quantity'),
                    'uom': item.stock_uom,
                    'rate': itm.get('rate'),
                    'amount': amount,
                    'income_account': default_income_account
                })
                total_amount += float(amount)
                
            if total_amount > 0:
                sales_invoice_doc.is_pos = 0
                sales_invoice_doc.flags.ignore_permissions = True
                sales_invoice_doc.set_missing_values()
                frappe.flags.ignore_account_permission = True
                sales_invoice_doc.save(ignore_permissions = True)
                sales_invoice_doc.submit()
                frappe.db.commit() 
                
                frappe.response.message = "Success. Order created"
            else:
                frappe.response.message = "Failed. Shop does not exist"
        else:
            frappe.response.message = "Failed. Order already created"
            
    except frappe.DoesNotExistError as e:
        frappe.log_error(frappe.get_traceback(), str(e))
        frappe.response.message = traceback.format_exc()
        frappe.response.error = str(e)
   
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), str(e))
        frappe.response.error = str(e)
        frappe.response.message = "Failed. Order not created"
    
def get_or_create_item(item):
    item_name = frappe.db.get_value("Item", item, "name")
    if item_name:
        return frappe.get_doc("Item", item_name)
    xitem = frappe.get_doc({
        "doctype": "Item",
        "item_name": item,
        "item_code": item,
        "weight_per_unit": 1,
        "stock_uom": "Nos",
        "weight_uom": "Nos",
        "item_group": "Products",
        "description": item,
    })
    xitem.save(ignore_permissions=True)
    return xitem