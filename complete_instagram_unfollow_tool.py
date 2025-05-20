from time import sleep
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.action_chains import ActionChains
import random
import getpass

class InstaBot:
    def __init__(self, username, password):
        # Configure Firefox options to appear more human-like
        options = Options()
        # Add user agent to appear more like a real browser
        options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        
        # Open Firefox with options
        self.browser = webdriver.Firefox(options=options)
        self.browser.maximize_window()  # Maximize to ensure elements are visible
        self.browser.implicitly_wait(10)
        self.wait = WebDriverWait(self.browser, 20)

        # Login to Instagram
        home_page = HomePage(self.browser, self.wait)
        success = home_page.login(username, password)
        
        if not success:
            print("Login failed!")
            self.browser.quit()
            return
            
        self.username = username

    def human_delay(self, min_delay=1, max_delay=3):
        """Add random delays to mimic human behavior"""
        delay = random.uniform(min_delay, max_delay)
        sleep(delay)

    def safe_click(self, element):
        """Safely click an element with multiple strategies"""
        try:
            # First try: Scroll element into view and click
            self.browser.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
            self.human_delay(1, 2)
            element.click()
            return True
        except:
            try:
                # Second try: Use JavaScript click
                self.browser.execute_script("arguments[0].click();", element)
                return True
            except:
                try:
                    # Third try: Use ActionChains
                    actions = ActionChains(self.browser)
                    actions.move_to_element(element).click().perform()
                    return True
                except:
                    print("All click methods failed for element")
                    return False

    def unfollow(self):
        # Go to your Instagram profile page
        profile_url = f"https://www.instagram.com/{self.username}/"
        print(f"Navigating to {profile_url}")
        self.browser.get(profile_url)
        self.human_delay(3, 5)

        # Wait for page to load completely
        try:
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "main")))
        except:
            print("Profile page didn't load properly")
            return

        # Get the usernames of all your followers
        followers, num_of_followers = self.get_followers()
        
        if followers is None:
            print("Failed to get followers list")
            return
        
        print(f"Found {len(followers)} followers out of {num_of_followers} total")
        
        # Check to make sure that approximately all followers were scraped
        if len(followers) < num_of_followers * 0.95:  # Reduced threshold to 95%
            print(f"Warning: Only scraped {len(followers)} out of {num_of_followers} followers")
            proceed = input("Continue anyway? (y/n): ")
            if proceed.lower() != 'y':
                return

        # Unfollow accounts that aren't following you
        num_of_accounts_unfollowed, accounts_unfollowed = self.compare_to_following_and_unfollow(followers)
        print(f"You've unfollowed {num_of_accounts_unfollowed} accounts.")
        self.human_delay()
        
        # Close browser
        self.browser.quit()

        # Store the usernames of accounts you've unfollowed 
        if accounts_unfollowed:
            with open('accounts_unfollowed.txt', 'w') as f:
                for account in accounts_unfollowed:
                    f.write(account + "\n")
            print(f"Saved unfollowed accounts to accounts_unfollowed.txt")

    def get_followers(self):
        try:
            print("Looking for followers link...")
            
            # Multiple strategies to find followers link
            followers_selectors = [
                "//a[contains(@href, '/followers/')]",
                "//a[contains(text(), 'followers')]",
                "//a[contains(text(), 'follower')]",
                ".//main//a[contains(@href, 'followers')]"
            ]
            
            followers_element = None
            for selector in followers_selectors:
                try:
                    followers_element = self.browser.find_element(By.XPATH, selector)
                    break
                except:
                    continue
            
            if not followers_element:
                print("Could not find followers link. Trying alternative method...")
                # Try to find by text pattern in the page
                page_source = self.browser.page_source
                if "followers" in page_source.lower():
                    print("Found followers text in page, but couldn't locate clickable element")
                return None, 0
            
            # Extract follower count from nearby text
            try:
                # Look for the follower count in various ways
                parent_element = followers_element.find_element(By.XPATH, "./..")
                followers_text = parent_element.text
                
                # Extract number from text like "1,234 followers"
                import re
                numbers = re.findall(r'[\d,]+', followers_text)
                if numbers:
                    num_of_followers = self.convert_str_to_num(numbers[0])
                else:
                    num_of_followers = 0
                    
            except:
                num_of_followers = 0
            
            print(f"Found followers element, estimated count: {num_of_followers}")
            
            # Click on followers using safe click method
            if not self.safe_click(followers_element):
                print("Failed to click followers link")
                return None, 0
                
            self.human_delay(3, 5)

            # Wait for the modal to appear with multiple possible selectors
            modal_selectors = [
                "[role='dialog']",
                "div[aria-labelledby]",
                ".x1n2onr6",  # Common Instagram modal class
                "//div[contains(@style, 'position: fixed')]"
            ]
            
            modal = None
            for selector in modal_selectors:
                try:
                    if selector.startswith("//"):
                        modal = self.wait.until(EC.presence_of_element_located((By.XPATH, selector)))
                    else:
                        modal = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    break
                except:
                    continue
            
            if not modal:
                print("Could not find followers modal")
                return None, 0
                
            print("Followers modal opened, starting to collect usernames...")
            
            # Collect followers with improved scrolling
            usernames_of_followers = set()
            last_count = 0
            no_change_count = 0
            
            while no_change_count < 5:  # Stop after 5 attempts with no new followers
                # Find follower links in the modal
                follower_links = self.browser.find_elements(By.CSS_SELECTOR, "[role='dialog'] a[href*='/']")
                
                current_usernames = set()
                for link in follower_links:
                    href = link.get_attribute('href')
                    if href and '/accounts/' not in href and '/explore/' not in href:
                        # Extract username from URL
                        username = href.rstrip('/').split('/')[-1]
                        if username and username != 'www.instagram.com' and len(username) > 0:
                            current_usernames.add(username)
                
                # Add new usernames
                usernames_of_followers.update(current_usernames)
                
                print(f"Collected {len(usernames_of_followers)} unique followers so far...")
                
                # Check if we found new followers
                if len(usernames_of_followers) == last_count:
                    no_change_count += 1
                else:
                    no_change_count = 0
                    last_count = len(usernames_of_followers)
                
                # Scroll within the modal
                self.browser.execute_script("""
                    const modal = document.querySelector('[role="dialog"]');
                    if (modal) {
                        const scrollable = modal.querySelector('div[style*="overflow"]') || modal;
                        scrollable.scrollTo(0, scrollable.scrollHeight);
                    }
                """)
                self.human_delay(2, 3)
            
            print(f"Done collecting followers. Total: {len(usernames_of_followers)}")

            # Close modal
            close_selectors = [
                "[role='dialog'] button[aria-label*='Close']",
                "[role='dialog'] svg[aria-label*='Close']",
                "//button//*[local-name()='svg']/*[local-name()='title' and contains(text(), 'Close')]/..",
                "[role='dialog'] button",
            ]
            
            for selector in close_selectors:
                try:
                    if selector.startswith("//"):
                        close_button = self.browser.find_element(By.XPATH, selector)
                    else:
                        close_button = self.browser.find_element(By.CSS_SELECTOR, selector)
                    
                    if self.safe_click(close_button):
                        break
                except:
                    continue
            
            self.human_delay(2, 3)
            return usernames_of_followers, num_of_followers
            
        except Exception as e:
            print(f"Error getting followers: {e}")
            import traceback
            traceback.print_exc()
            return None, 0

    def convert_str_to_num(self, num_as_str):
        num_map = {'K': 1000, 'M': 1000000, 'B': 1000000000}
        num_as_str = str(num_as_str).replace(",", "").replace(" ", "")

        if not num_as_str:
            return 0
            
        last_ch = num_as_str[-1].upper()
        if last_ch in num_map:
            try:
                num_as_int = float(num_as_str[:-1])
                num_as_int *= num_map[last_ch]
                num_as_int = int(num_as_int)
            except:
                num_as_int = 0
        else:
            try:
                num_as_int = int(num_as_str)
            except:
                num_as_int = 0

        return num_as_int

    def compare_to_following_and_unfollow(self, followers):
        try:
            print("Looking for following link...")
            
            # Navigate back to profile if needed
            if f"/{self.username}/" not in self.browser.current_url:
                self.browser.get(f"https://www.instagram.com/{self.username}/")
                self.human_delay(3, 5)
            
            # Find following link
            following_selectors = [
                "//a[contains(@href, '/following/')]",
                "//a[contains(text(), 'following')]",
                ".//main//a[contains(@href, 'following')]"
            ]
            
            following_element = None
            for selector in following_selectors:
                try:
                    following_element = self.browser.find_element(By.XPATH, selector)
                    break
                except:
                    continue
            
            if not following_element:
                print("Could not find following link")
                return 0, set()
            
            # Click on following
            if not self.safe_click(following_element):
                print("Failed to click following link")
                return 0, set()
                
            self.human_delay(3, 5)

            # Wait for modal
            try:
                self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[role='dialog']")))
            except:
                print("Following modal did not open")
                return 0, set()

            print("Following modal opened, starting to unfollow...")

            # Unfollow accounts that don't follow back
            accounts_unfollowed = self.unfollow_helper(followers)

            # Close modal
            try:
                close_button = self.browser.find_element(By.CSS_SELECTOR, "[role='dialog'] button[aria-label*='Close']")
                self.safe_click(close_button)
            except:
                # Try alternative close methods
                try:
                    self.browser.send_keys(Keys.ESCAPE)
                except:
                    pass

            self.human_delay(2, 3)

            return len(accounts_unfollowed), accounts_unfollowed
            
        except Exception as e:
            print(f"Error in compare_to_following_and_unfollow: {e}")
            import traceback
            traceback.print_exc()
            return 0, set()

    def unfollow_helper(self, followers):
        accounts_unfollowed = set()
        unfollow_count = 0
        max_unfollows = 500  # Increased for mass unfollow
    
        try:
            print("Starting unfollow process...")
            
            # Wait a bit for the modal to fully load
            self.human_delay(5, 8)
            
            # Check if modal is actually open
            modal = self.browser.find_elements(By.CSS_SELECTOR, "[role='dialog']")
            if not modal:
                print("ERROR: Following modal not found!")
                return accounts_unfollowed
            
            print(f"Modal found, starting unfollow process (max: {max_unfollows})")
            
            processed_users = set()  # Track all processed users to avoid duplicates
            scroll_attempts = 0
            max_scroll_attempts = 15
            
            while unfollow_count < max_unfollows and scroll_attempts < max_scroll_attempts:
                # Get all visible entries
                following_entries = self.browser.find_elements(By.CSS_SELECTOR, "[role='dialog'] [role='listitem']")
                
                if not following_entries:
                    # Try alternative selectors
                    alternative_selectors = [
                        "[role='dialog'] div[style*='overflow'] > div > div",
                        "[role='dialog'] ul li",
                        "[role='dialog'] div[role='listitem']",
                        "[role='dialog'] > div > div > div:nth-child(2) > div > div"
                    ]
                    
                    for selector in alternative_selectors:
                        following_entries = self.browser.find_elements(By.CSS_SELECTOR, selector)
                        if following_entries:
                            print(f"Found {len(following_entries)} entries with selector: {selector}")
                            break
                
                if not following_entries:
                    print(f"No entries found on attempt {scroll_attempts + 1}")
                    scroll_attempts += 1
                    # Different scrolling strategy
                    self.browser.execute_script("""
                        const modal = document.querySelector('[role="dialog"]');
                        if (modal) {
                            const scrollable = modal.querySelector('div[style*="overflow"]') || 
                                            modal.querySelector('div[style*="scroll"]') || 
                                            modal;
                            scrollable.scrollTo(0, scrollable.scrollHeight);
                        }
                    """)
                    self.human_delay(3, 5)
                    continue
                
                print(f"Attempt {scroll_attempts + 1}: Found {len(following_entries)} total entries")
                
                entries_processed_this_round = 0
                new_entries_found = 0
                
                # Process ALL visible entries, not just first 5
                for i, entry in enumerate(following_entries):
                    if unfollow_count >= max_unfollows:
                        break
                    
                    try:
                        # Get username
                        username_links = entry.find_elements(By.CSS_SELECTOR, "a[href*='/']")
                        if not username_links:
                            continue
                        
                        href = username_links[0].get_attribute('href')
                        if not href:
                            continue
                            
                        username = href.rstrip('/').split('/')[-1]
                        
                        # Skip if we've already seen this user
                        if username in processed_users:
                            continue
                        
                        processed_users.add(username)
                        new_entries_found += 1
                        
                        print(f"  Processing new user: {username}")
                        
                        # Check if follows back
                        if username in followers:
                            print(f"    {username} follows back, skipping")
                            continue
                        
                        # Find unfollow button
                        buttons = entry.find_elements(By.CSS_SELECTOR, "button")
                        unfollow_button = None
                        
                        for button in buttons:
                            button_text = button.text.lower()
                            if "following" in button_text:
                                unfollow_button = button
                                break
                        
                        if not unfollow_button:
                            print(f"    No unfollow button found for {username}")
                            continue
                        
                        print(f"    Attempting to unfollow {username}")
                        
                        # Click unfollow
                        if self.safe_click(unfollow_button):
                            self.human_delay(1, 2)
                            
                            # Look for confirmation
                            try:
                                confirm_button = self.wait.until(
                                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Unfollow')]"))
                                )
                                if self.safe_click(confirm_button):
                                    accounts_unfollowed.add(username)
                                    unfollow_count += 1
                                    entries_processed_this_round += 1
                                    print(f"    ✓ Successfully unfollowed {username} ({unfollow_count}/{max_unfollows})")
                                    self.human_delay(2, 4)  # Delay after successful unfollow
                            except:
                                print(f"    Failed to confirm unfollow for {username}")
                                # Try to close any popup
                                try:
                                    cancel_buttons = self.browser.find_elements(By.XPATH, "//button[contains(text(), 'Cancel')]")
                                    if cancel_buttons:
                                        self.safe_click(cancel_buttons[0])
                                except:
                                    pass
                        else:
                            print(f"    Failed to click unfollow button for {username}")
                            
                    except Exception as e:
                        print(f"    Error processing entry: {e}")
                        continue
                
                print(f"Round {scroll_attempts + 1}: Processed {entries_processed_this_round} unfollows, found {new_entries_found} new entries")
                
                # Update scroll attempts based on progress
                if new_entries_found == 0:
                    scroll_attempts += 1
                    print(f"No new entries found, scroll attempt {scroll_attempts}")
                else:
                    scroll_attempts = 0  # Reset if we found new entries
                    print(f"Found new entries, resetting scroll counter")
                
                # Enhanced scrolling strategy
                if unfollow_count < max_unfollows:
                    print("Scrolling for more entries...")
                    
                    # Try multiple scrolling methods
                    scroll_scripts = [
                        """
                        const modal = document.querySelector('[role="dialog"]');
                        if (modal) {
                            const scrollable = modal.querySelector('div[style*="overflow"]') || modal;
                            scrollable.scrollTo(0, scrollable.scrollHeight);
                        }
                        """,
                        """
                        const modal = document.querySelector('[role="dialog"]');
                        if (modal) {
                            modal.scrollTo(0, modal.scrollHeight);
                        }
                        """,
                        """
                        const scrollable = document.querySelector('[role="dialog"] div[style*="overflow"]');
                        if (scrollable) {
                            scrollable.scrollTop = scrollable.scrollHeight;
                        }
                        """
                    ]
                    
                    for script in scroll_scripts:
                        self.browser.execute_script(script)
                        self.human_delay(1, 2)
                    
                    self.human_delay(2, 3)
                    
        except Exception as e:
            print(f"Major error in unfollow_helper: {e}")
            import traceback
            traceback.print_exc()
            
        print(f"Unfollow process completed. Total unfollowed: {len(accounts_unfollowed)}")
        print(f"Total unique users processed: {len(processed_users)}")
        return accounts_unfollowed


class HomePage:
    def __init__(self, browser, wait):
        self.browser = browser
        self.wait = wait
        self.browser.get("https://www.instagram.com/")

    def login(self, username, password):
        try:
            # Wait for and find the username and password inputs
            username_input = self.wait.until(
                EC.presence_of_element_located((By.NAME, "username"))
            )
            password_input = self.wait.until(
                EC.presence_of_element_located((By.NAME, "password"))
            )

            # Clear and type credentials with human-like delays
            username_input.clear()
            self.type_like_human(username_input, username)
            
            sleep(1)
            
            password_input.clear()
            self.type_like_human(password_input, password)

            sleep(2)

            # Find and click login button
            login_button = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']"))
            )
            login_button.click()

            # Wait for login to complete - check for either success or error
            try:
                # Wait for navigation away from login page
                self.wait.until(
                    lambda driver: "/accounts/login" not in driver.current_url
                )
                
                print("Login successful!")
                
                # Handle "Save login info" prompt if it appears
                try:
                    not_now_button = self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Not Now') or contains(text(), 'Not now')]"))
                    )
                    not_now_button.click()
                except:
                    pass
                
                # Handle "Turn on notifications" prompt if it appears
                try:
                    not_now_button = self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Not Now') or contains(text(), 'Not now')]"))
                    )
                    not_now_button.click()
                except:
                    pass
                
                return True
                    
            except Exception as e:
                print(f"Login may have failed or timed out: {e}")
                return False
                
        except Exception as e:
            print(f"Error during login: {e}")
            import traceback
            traceback.print_exc()
            return False

    def type_like_human(self, element, text):
        """Type text with random delays to mimic human typing"""
        for char in text:
            element.send_keys(char)
            sleep(random.uniform(0.05, 0.2))


# Safe usage without hardcoded credentials
if __name__ == "__main__":
    print("Instagram Unfollow Tool")
    print("======================")
    print("WARNING: This tool automates Instagram actions.")
    print("Use responsibly and be aware of Instagram's Terms of Service.")
    print()
    
    username = input("Enter your Instagram username: ")
    password = getpass.getpass("Enter your Instagram password: ")
    
    confirm = input(f"Proceed to unfollow non-followers for @{username}? (y/n): ")
    if confirm.lower() != 'y':
        print("Cancelled.")
        exit()
    
    try:
        my_insta_bot = InstaBot(username, password)
        if hasattr(my_insta_bot, 'browser'):  # Check if bot initialized successfully
            my_insta_bot.unfollow()
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
