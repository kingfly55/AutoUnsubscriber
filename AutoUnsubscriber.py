#! python3

import getpass
import logging
import re
import sys
import webbrowser

import bs4
import imapclient
import pyzmail
from tqdm import tqdm

# --- Configuration & Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("unsubscriber.log"), logging.StreamHandler()],
)

"""List of common service providers and respective imap links"""
servers = [
    ("Gmail", "imap.gmail.com"),
    ("Outlook", "imap-mail.outlook.com"),
    ("Hotmail", "imap-mail.outlook.com"),
    ("Yahoo", "imap.mail.yahoo.com"),
    ("ATT", "imap.mail.att.net"),
    ("Comcast", "imap.comcast.net"),
    ("Verizon", "incoming.verizon.net"),
    ("AOL", "imap.aol.com"),
    ("Zoho", "imap.zoho.com"),
]

"""Key words for unsubscribe link"""
words = ["unsubscribe", "subscription", "optout"]


class AutoUnsubscriber:
    def __init__(self):
        self.email = ""
        self.user = None
        self.password = ""
        self.imap = None
        self.goToLinks = False
        self.delEmails = False
        self.senderList = []
        self.noLinkList = []
        self.wordCheck = []
        self.providers = []

        # Regex compilation
        for i in range(len(servers)):
            self.providers.append(re.compile(servers[i][0], re.I))

        for i in range(len(words)):
            self.wordCheck.append(re.compile(words[i], re.I))

    """Get initial user info"""

    def getInfo(self):
        logging.info("Starting AutoUnsubscriber...")
        print(
            "Auto-detected providers: Gmail, Outlook, Hotmail, Yahoo, AOL, Zoho, AT&T, Comcast, Verizon"
        )

        getEmail = True
        while getEmail:
            self.email = input("\nEnter your email address: ")
            found_provider = False

            # Check against known providers
            for j in range(len(self.providers)):
                if self.providers[j].search(self.email):
                    self.user = servers[j]
                    logging.info(f"Detected provider: {self.user[0]}")
                    found_provider = True
                    getEmail = False
                    break

            # Manual Override if not found
            if not found_provider:
                print("\nProvider not auto-detected.")
                manual = input(
                    "Enter your IMAP server manually (e.g., imap.fastmail.com) or press Enter to retry email: "
                )
                if manual.strip():
                    # Format: (CustomName, IMAP Address)
                    self.user = ("Custom", manual.strip())
                    logging.info(f"Using manual provider: {self.user[1]}")
                    getEmail = False

        self.password = getpass.getpass(f"Enter password for {self.email}: ")

    """Log in to IMAP server"""

    def login(self, read=True):
        try:
            logging.info(f"Connecting to {self.user[1]}...")
            self.imap = imapclient.IMAPClient(self.user[1], ssl=True)
            self.imap._MAXLINE = 10000000
            self.imap.login(self.email, self.password)
            self.imap.select_folder("INBOX", readonly=read)
            logging.info(f"Login successful. Read-only mode: {read}")
            return True
        except Exception as e:
            logging.error(f"Login failed: {e}")
            return False

    """Attempt to log in to server"""

    def accessServer(self, readonly=True):
        if self.email == "":
            self.getInfo()
        attempt = self.login(readonly)
        if attempt == False:
            print("Login failed. Let's try again.")
            self.newEmail()
            self.accessServer(readonly)

    """Search for emails and parse for links"""

    def getEmails(self):
        logging.info("Searching INBOX for 'unsubscribe' keyword...")

        try:
            # FIX 1: Split search terms for stricter IMAP servers (Zoho, etc.)
            UIDs = self.imap.search(["BODY", "unsubscribe"])
            total_emails = len(UIDs)
            logging.info(
                f"Found {total_emails} emails containing 'unsubscribe'. Fetching data in batches..."
            )

            # FIX 2: Process in batches to avoid server timeouts/socket errors
            batch_size = 50

            # Initialize progress bar for the total count
            pbar = tqdm(total=total_emails, desc="Scanning Emails", unit="email")

            # Loop through UIDs in chunks
            for i in range(0, total_emails, batch_size):
                batch_UIDs = UIDs[i : i + batch_size]

                try:
                    raw = self.imap.fetch(batch_UIDs, ["BODY[]"])

                    for UID in batch_UIDs:
                        if UID not in raw:
                            continue

                        msg = pyzmail.PyzMessage.factory(raw[UID][b"BODY[]"])
                        sender = msg.get_addresses("from")

                        if not sender:
                            pbar.update(1)
                            continue

                        # Check duplication
                        trySender = True
                        for spammers in self.senderList:
                            if sender[0][1] in spammers:
                                trySender = False

                        if trySender:
                            try:
                                senderName = (
                                    sender[0][0].encode("cp437", "ignore")
                                ).decode("cp437")
                            except:
                                senderName = "Unknown Sender"

                            url = False
                            if msg.html_part != None:
                                try:
                                    html = msg.html_part.get_payload().decode(
                                        "utf-8", errors="ignore"
                                    )
                                    soup = bs4.BeautifulSoup(html, "html.parser")
                                    elems = soup.select("a")

                                    for k in range(len(elems)):
                                        for j in range(len(self.wordCheck)):
                                            if self.wordCheck[j].search(str(elems[k])):
                                                url = elems[k].get("href")
                                                break
                                        if url:
                                            break
                                except Exception:
                                    pass

                            if url:
                                self.senderList.append(
                                    [senderName, sender[0][1], url, False, False]
                                )
                            else:
                                notInList = True
                                for noLinkers in self.noLinkList:
                                    if sender[0][1] in noLinkers:
                                        notInList = False
                                if notInList:
                                    self.noLinkList.append([sender[0][0], sender[0][1]])

                        pbar.update(1)

                except Exception as batch_err:
                    logging.error(
                        f"Error processing batch starting at index {i}: {batch_err}"
                    )
                    continue

            pbar.close()
            logging.info(
                f"Scan complete. Found {len(self.senderList)} unique senders with links."
            )
            self.imap.logout()

        except Exception as e:
            logging.error(f"Critical error during email fetching: {e}")

    """Display info"""

    def displayEmailInfo(self):
        print("\n" + "=" * 40)
        print("          SCAN RESULTS          ")
        print("=" * 40)

        if self.noLinkList:
            print(
                f"\n[!] Senders found (but NO unsubscribe link detected): {len(self.noLinkList)}"
            )

        if self.senderList:
            print(f"\n[+] Senders found WITH unsubscribe links: {len(self.senderList)}")
            for i, sender in enumerate(self.senderList):
                print(f" {i + 1}. {sender[0]} ({sender[1]})")

    """User Decisions"""

    def decisions(self):
        def choice(userInput):
            if userInput.lower() == "y":
                return True
            elif userInput.lower() == "n":
                return False
            else:
                return None

        self.displayEmailInfo()

        if not self.senderList:
            return

        print("\n--- Decision Time ---")
        print("Review the list above. You can choose to open links or delete emails.")

        mode = input(
            "\nType 'all' to process all senders, or 'each' to decide one by one: "
        ).lower()

        if mode == "all":
            open_all = choice(input("Open ALL unsubscribe links? (Y/N): "))
            del_all = choice(input("Delete ALL emails from these senders? (Y/N): "))

            for item in self.senderList:
                if open_all:
                    item[3] = True
                    self.goToLinks = True
                if del_all:
                    item[4] = True
                    self.delEmails = True
        else:
            for j in range(len(self.senderList)):
                print(f"\nSender: {self.senderList[j][0]}")
                while True:
                    unsub = input("  Open unsubscribe link? (Y/N): ")
                    c = choice(unsub)
                    if c is not None:
                        if c:
                            self.senderList[j][3] = True
                            self.goToLinks = True
                        break

                while True:
                    delete = input("  Delete emails from this sender? (Y/N): ")
                    d = choice(delete)
                    if d is not None:
                        if d:
                            self.senderList[j][4] = True
                            self.delEmails = True
                        break

    """Open Links"""

    def openLinks(self):
        if not self.goToLinks:
            return

        logging.info("Opening unsubscribe links...")
        links_to_open = [s[2] for s in self.senderList if s[3]]

        batch_size = 10
        for i in range(0, len(links_to_open), batch_size):
            batch = links_to_open[i : i + batch_size]
            print(
                f"\nOpening batch {i // batch_size + 1} of {(len(links_to_open) // batch_size) + 1}..."
            )

            for link in batch:
                webbrowser.open(link)

            if i + batch_size < len(links_to_open):
                input("Paused. Press 'Enter' to open the next batch of links...")

    """Delete Emails (Optimized)"""

    def deleteEmails(self):
        if not self.delEmails:
            return

        targets = [s[1] for s in self.senderList if s[4]]
        print(
            f"\n[WARNING] You have selected to delete emails from {len(targets)} senders."
        )
        print("These cannot be recovered.")
        confirm = input("Type 'DELETE' to confirm: ")

        if confirm != "DELETE":
            logging.info("Deletion cancelled by user.")
            return

        logging.info("Logging in for deletion (Write Mode)...")
        if not self.login(False):
            return

        total_marked = 0

        for sender_data in tqdm(self.senderList, desc="Processing Deletions"):
            if sender_data[4] == True:
                email_addr = sender_data[1]

                # Split search terms for server compatibility
                DelUIDs = self.imap.search(["BODY", "unsubscribe", "FROM", email_addr])

                if DelUIDs:
                    self.imap.delete_messages(DelUIDs)
                    total_marked += len(DelUIDs)

        if total_marked > 0:
            logging.info(f"Expunging {total_marked} messages from server...")
            self.imap.expunge()
            logging.info("Expunge complete.")
        else:
            logging.info("No messages found to delete.")

        self.imap.logout()

    def runAgain(self):
        self.goToLinks = False
        self.delEmails = False
        self.senderList = []
        self.noLinkList = []

    def newEmail(self):
        self.email = ""
        self.user = None
        self.password = ""
        self.imap = None
        self.runAgain()

    def nextMove(self):
        print("\n" + "-" * 30)
        while True:
            print(f"Current Email: {self.email}")
            print(" [A] Run again on same email")
            print(" [D] Different email")
            print(" [Q] Quit")
            choice = input("Choice: ").lower()

            if choice == "a":
                self.runAgain()
                return True
            elif choice == "d":
                self.newEmail()
                return False
            elif choice == "q":
                logging.info("Exiting program.")
                sys.exit()

    def fullProcess(self):
        self.accessServer()
        self.getEmails()
        if self.senderList:
            self.decisions()
            self.openLinks()
            self.deleteEmails()
        else:
            logging.info("No unsubscribe links detected in search.")

    def usageLoop(self):
        self.fullProcess()
        while True:
            self.nextMove()
            self.fullProcess()


def main():
    try:
        Auto = AutoUnsubscriber()
        Auto.usageLoop()
    except KeyboardInterrupt:
        print("\nProgram interrupted by user.")
        sys.exit()


if __name__ == "__main__":
    main()
