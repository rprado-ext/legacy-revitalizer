None
import datetime
# Global variables (Bad practice)
l = []
d = {"u": "admin", "p": "12345"}

def fn(a, b):
    """
    Perform an action on the global item list.

    This function handles multiple unrelated responsibilities depending on the
    value of `a`:
    - "add": Appends a new item with an auto-incremented id, the given value,
      and the current timestamp to the global list `l`.
    - "show": Prints all items currently stored in `l` to stdout.
    - "save": Serializes `l` as a string and writes it to "data.txt".

    Args:
        a (str): The action to perform. One of "add", "show", or "save".
        b: The value to store when `a` is "add". Ignored for other actions.

    Side effects:
        - Mutates the global list `l` when `a` is "add".
        - Prints to stdout for all recognized actions.
        - Writes to "data.txt" when `a` is "save".
    """
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
    """
    Validate a username and password against hardcoded credentials.

    Compares the provided credentials against the global dict `d`, which
    stores a single hardcoded username/password pair.

    Args:
        u (str): The username to validate.
        p (str): The password to validate.

    Returns:
        bool: True if both username and password match the stored credentials,
              False otherwise.

    Security note:
        Credentials are stored in plaintext in a global variable. This is
        insecure and should not be used in production.
    """
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
    """
    Compute the sum of all integers from 0 to x-1 (triangular number).

    This function is unused dead code and has no callers in the module.

    Args:
        x (int): The exclusive upper bound of the summation range.

    Returns:
        int: The sum of integers 0 + 1 + 2 + ... + (x - 1).
    """
    res = 0
    for i in range(x):
        res += i
    return res
