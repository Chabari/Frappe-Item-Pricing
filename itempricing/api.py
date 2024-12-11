   
import frappe 

@frappe.whitelist()
def set_data_price(data):
    message = "Saving"
    try:
        doc = frappe.get_doc("Item Price Settings", data)
        
        frappe.publish_realtime('msgprint', 'Starting background job...')
        conditions = ""
        if doc.item_group:
            itemgroup = doc.item_group
            conditions += """ AND `tabItem`.item_group = '{0}'""".format(itemgroup)
    
        if doc.base_price_list:
            base_price_list = doc.base_price_list
            conditions += """ AND `tabItem Price`.price_list = '{0}'""".format(base_price_list)
        else:
            if doc.price_list:
                price_list = doc.price_list
                conditions += """ AND `tabItem Price`.price_list = '{0}'""".format(price_list)
        if doc.supplier:
            supplier = doc.supplier
            conditions += """ AND `tabItem Default`.default_supplier = '{0}'""".format(supplier)

        prices_data = []
        items_data = frappe.db.sql(
            """
            SELECT
                `tabItem Price`.name AS price_name,
                `tabItem Price`.price_list_rate,
                `tabItem Price`.price_list AS price_list_name,
                `tabItem`.name AS item_code,
                `tabItem`.item_name,
                `tabItem`.item_group,
                `tabItem Default`.default_supplier
            FROM
                `tabItem Price` 
                LEFT JOIN `tabItem`
                    ON `tabItem Price`.item_code = `tabItem`.name
                    
                LEFT JOIN `tabItem Default`
                    ON `tabItem Default`.parent = `tabItem`.name
            WHERE
                `tabItem`.disabled = 0
                    {0}
                """.format(
                    conditions or ""
            ),
            as_dict=1,
        )
        
        for d in items_data:
            finalprice = 0
            if d.price_list_rate:
                if doc.change_type == "Percentage Rate":
                    if doc.price_type == "Price Increase":
                        finalprice = ((doc.rate + 100) / 100) * d.price_list_rate
                    else:
                        finalprice = ((100 - doc.rate) / 100) * d.price_list_rate
                else:
                    if doc.price_type == "Price Increase":
                        finalprice = doc.rate + d.price_list_rate
                    else:
                        finalprice = d.price_list_rate - doc.rate
            
            prices_data.append(frappe._dict({
                'item_code': d.item_code,
                'item_group': d.item_group,
                'price_list': d.price_list_name,
                'item_price': d.price_name,
                'initial_price': d.price_list_rate,
                'default_supplier': d.default_supplier,
                'actual_price': finalprice,
            }))
        if prices_data:
            doc.set('items', prices_data)
            doc.status = "Saved"
            doc.save()
            message = "Saved Items"
            frappe.publish_realtime('msgprint', 'Background job has ended...')
    except Exception as e:
        print(e)
        message = str(e)
        # frappe.throw(_("Error."+str(e)))
    return message


@frappe.whitelist()
def submit_item_price(data):
    message = "Saving"
    try:
        doc = frappe.get_doc("Item Price Settings", data)
        
        frappe.publish_realtime('msgprint', 'Starting background job...')
        
        for xd in doc.items:
            
            x_item_price = frappe.db.get_value('Item Price', {'price_list': doc.price_list, 'item_code': xd.item_code}, ['name'], as_dict=1)
            if x_item_price:
                item_price = frappe.get_doc("Item Price", x_item_price.name)
            else:
                item_price = frappe.new_doc("Item Price")
                item_price.price_list = doc.price_list
                item_price.item_code = xd.item_code
            item_price.price_list_rate = xd.actual_price
            item_price.insert()
            
            # pricelist = frappe.get_doc("Price List", item_price.price_list)
            # if item_price.disabled == 0 and pricelist.enabled == 1:
            # item_price.price_list_rate = xd.actual_price
            # item_price.save()
            
        frappe.publish_realtime('msgprint', 'Background job has ended...')
        message = "Data saved"
    except Exception as e:
        print(e)
        message = str(e)
        # frappe.throw(_("Error."+str(e)))
    return message
