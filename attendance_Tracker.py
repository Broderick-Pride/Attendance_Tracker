print("Initializing Attendance Tracker")
import sqlite3
from unicodedata import name
con = sqlite3.connect('attendance_tracker.db')
if con:    print("Database connection successful")
else:    print("Database connection failed")
cur = con.cursor()
cur.execute('''CREATE TABLE IF NOT EXISTS members
               (id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                attendance_count INTEGER DEFAULT 0)''')
con.commit()
def main():
    print("Initializing Terminal Menu", "\n", "Welcome" ,"\n", "Please select an option from the menu below:")
    print("1. Add New Unit Member", "\n", "2. Delete Unit Member", "\n", "3. View Attendance Records", "\n",
           "4. Record Attendance", "\n", "5. Exit")
    user_input = int(input("Enter your choice: "))
    if user_input == 1:
        New_Member()
    elif user_input == 2:
        print("Deleting Unit Member")
        name = input("Enter the name of the unit member to delete: ")
        # Code to delete the unit member from the database or list
        cur.execute("DELETE FROM members WHERE name = ?", (name,))
        con.commit()
        main()
    elif user_input == 3:
        print("Viewing Attendance Records")
        # Code to display attendance records for all unit members
        cur.execute("SELECT name, attendance_count FROM members")
        records = cur.fetchall()
        for record in records:
            print(f"Name: {record[0]}, Attendance Count: {record[1]}")
        main()
    elif user_input == 4:
        Record_Attendance()
    elif user_input == 5:
        print("Exiting the program. Goodbye!")
        con.close()
        exit()
    else:
        print("Invalid choice. Please select a valid option from the menu.")


########################################## Function Definitions ####################################################
def New_Member():
    print("Adding New Unit Member")
    member_name = input("Enter the name of the new unit member: ")
    # Code to add the new unit member to the database or list
    cur.execute("INSERT INTO members (name, attendance_count) VALUES (?, ?)", (member_name, 0))
    con.commit()
    repeat = input("Do you want to add another member? (yes/no): ")
    if repeat.lower() == 'yes':
        New_Member()
    elif repeat.lower() == 'no':
        main()
    else:
        print("Invalid choice. Please select a valid option from the menu.")
#############
def Delete_Member():
    print("Deleting Unit Member")
    name = input("Enter the name of the unit member to delete: ")
    # Code to delete the unit member from the database or list
    cur.execute("DELETE FROM members WHERE name = ?", (name,))
    con.commit()
    repeat = input("Do you want to delete another member? (yes/no): ")
    if repeat.lower() == 'yes':
        Delete_Member()
    elif repeat.lower() == 'no':
        main()
    else:
        print("Invalid choice. Please select a valid option from the menu.")
###########################################
def View_Attendance():
    print("Viewing Attendance Records")
    # Code to display attendance records for all unit members
    cur.execute("SELECT name, attendance_count FROM members")
    records = cur.fetchall()
    for record in records:
        print(f"Name: {record[0]}, Attendance Count: {record[1]}")
    main()
##############################
def Record_Attendance():
    print("Recording Attendance")
    name = input("Enter the name of the unit member to record attendance for: ")
        # Code to update the attendance record for the specified unit member
    cur.execute("UPDATE members SET attendance_count = attendance_count + 1 WHERE name = ?", (name,))
    con.commit()
    repeat = input("Do you want to record attendance for another member? (yes/no): ")
    if repeat.lower() == 'yes':
        Record_Attendance()
    elif repeat.lower() == 'no':
        main()
    else:
        print("Invalid choice. Please select a valid option from the menu.")

main()