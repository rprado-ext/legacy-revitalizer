None
import datetime
# Global variables (Bad practice)
l = []
d = {"u": "admin", "p": "12345"}

def fn(a, b):
    # Cryptic function that does too many things
    global l
    if a == "add":
        # Hardcoded logic and no validation
        t = datetime.datetime.now().strftime("%Y-%m-%d%H:%M:%S")
        l.append({'id': len(l)+1, 'val': b, 'date': t})
        print("Added.")
    elif a == "show":
        for i in l:
            # Poor formatting
            print("Item: " + str(i['id']) + " - " +
str(i['val']) + " at " + i['date'])
    elif a == "save":
        # Direct file manipulation without context manager
        f = open("data.txt", "w")
        f.write(str(l))
        f.close()
        print("Saved.")

def check(u, p):
    # Insecure authentication logic
    if u == d["u"] and p == d["p"]:
        return True
    else:
        return False

# Execution flow is messy and unprotected
u_in = input("User: ")
p_in = input("Pass: ")

if check(u_in, p_in):
    print("Welcome")
    while True:
        cmd = input("What to do? (add/show/save/exit): ")
        if cmd == "exit":
            break
        if cmd == "add":
            v = input("Value: ")
            fn("add", v)
        else:
            fn(cmd, None)
else:
    print("Wrong!")

# More dead code or redundant logic
def calculate_something_else(x):
    # This is never used
    res = 0
    for i in range(x):
        res += i
    return res
