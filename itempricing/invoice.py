from erpnext.stock.doctype.batch.batch import get_batch_no, get_batch_qty, set_batch_nos
from frappe.utils import flt
from frappe.utils import flt, cint, getdate, get_datetime, nowdate, nowtime, add_days, unique, month_diff
import traceback
from erpnext import get_default_company
from etims.utils import *


def get_main_company():
    return frappe.get_doc("Company", get_default_company())

@frappe.whitelist(allow_guest=True)  
def create(**args):
    try:
        sales_invoice_doc = frappe.db.get_value('Sales Invoice', {'custom_order_id': str(args.get('order_id'))}, ['name'], as_dict=1) 
        if not sales_invoice_doc:
            
            sales_invoice_doc = frappe.new_doc('Sales Invoice')
            company = get_main_company()
            customer = check_customer(args.get('customer_name') or 'Walk-in Customer')
            sales_invoice_doc.discount_amount = 0
            sales_invoice_doc.customer = customer.name
            sales_invoice_doc.due_date = frappe.utils.data.today()
            sales_invoice_doc.debit_to = company.default_receivable_account
            sales_invoice_doc.custom_order_id = str(args.get('order_id'))
            sales_invoice_doc.update_stock = 0
            
            pos_profile = frappe.db.get_value('POS Profile', {}, ['name', 'income_account'], as_dict=1) 
            default_income_account = pos_profile.income_account

                       
            total_amount = 0
            
            for itm in args.get('items'):
                item = get_or_create_item(itm.get('item_name'))          
                           
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
                sales_invoice_doc.paid_amount = total_amount
                    
                payments = []
                
                # create a POS Profile for the same..................
                
                payments.append(frappe._dict({
                    'mode_of_payment': "Cash",
                    'amount': total_amount
                }))
                sales_invoice_doc.set("payments", payments)
                
                sales_invoice_doc.custom_send_for_signing = 0
                sales_invoice_doc.flags.ignore_permissions = True
                sales_invoice_doc.set_missing_values()
                frappe.flags.ignore_account_permission = True
                sales_invoice_doc.insert(ignore_permissions = True)
                sales_invoice_doc.submit()
                frappe.db.commit() 
                return send_signing(sales_invoice_doc)
                
            else:
                frappe.response.success = False
                frappe.response.message = "Failed. Shop does not exist"
        else:
            frappe.response.success = False
            frappe.response.message = "Failed. Order already created"
            
    except frappe.DoesNotExistError as e:
        frappe.response.success = False
        frappe.log_error(frappe.get_traceback(), str(e))
        frappe.response.message = traceback.format_exc()
        frappe.response.error = str(e)
   
    except Exception as e:
        
        frappe.response.success = False
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
    payload = get_item_payloan(xitem)
    res = post('/items', payload)
    if res and res['status'] == 200:
        xitem.custom_etims_item_code = res['data']['itemCode']
        xitem.save(ignore_permissions = True)
    return xitem

def check_customer(name):
    customer = frappe.db.get_value("Customer", name, "name")
    if customer:
        return frappe.get_doc("Customer", customer)
    xcustomer = frappe.get_doc({
        "doctype": "Customer",
        "customer_name": name,
        "customer_type": "Company",
        "territory": "Kenya",
        "customer_group": "Commercial"
    })
    xcustomer.save(ignore_permissions=True)
    return xcustomer
    
def send_signing(doc):
    included_in_print_rate = 1
    if doc.get("taxes"):
        for tax in doc.taxes:
            included_in_print_rate = tax.included_in_print_rate
    res = sign_invoice(doc, included_in_print_rate)
    if res and res['status'] == 200:
        doc.custom_etims_invoice_no = str(res['data']['invoiceNo'])
        doc.custom_etims_internal_data = res['data']['internalData']
        doc.custom_etims_signature = res['data']['signature']
        doc.custom_etims_scdc_id = res['data']['scdcId']
        doc.custom_etims_scu_receipt_date = res['data']['scuReceiptDate']
        doc.custom_etims_scu_receipt_no = str(res['data']['scuReceiptNo'])
        doc.custom_etims_invoiceverification_url = res['data']['invoiceVerificationUrl']
        doc.db_update()
        data = {
            "invoiceNo": str(res['data']['invoiceNo']),
            "internalData": str(res['data']['internalData']),
            "signature": str(res['data']['signature']),
            "scdcId": str(res['data']['scdcId']),
            "scuReceiptDate": str(res['data']['scuReceiptDate']),
            "scuReceiptNo": str(res['data']['scuReceiptNo']),
            "invoiceVerificationUrl": str(res['data']['invoiceVerificationUrl']),
        }
        frappe.response.data = data
    frappe.response.success = True
    frappe.response.message = "Success. Order created"
    return