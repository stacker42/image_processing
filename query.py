from __future__ import print_function
import pymysql

connection = pymysql.connect(host='localhost',
                             user='imageportal',
                             password='',
                             db='imageportal',
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor)

with connection.cursor() as cursor:
    alpha_j2000 = float(input("Enter RA (J2000): "))
    delta_j2000 = float(input("Enter Dec (J2000): "))
    # Get all relevant records, with the original filter and the target name
    query = "SELECT p.*, o.orignal_filter, t.name FROM photometry as p, observations as o, objects as t WHERE (p.alpha_j2000 BETWEEN %s AND %s) AND (p.delta_j2000 BETWEEN %s AND %s) AND p.observation_id = o.id AND t.number = o.target_id"
    cursor.execute(query, (alpha_j2000 - 0.003, alpha_j2000 + 0.003, delta_j2000 - 0.003, delta_j2000 + 0.003,))
    result = cursor.fetchall()
    print(result)
