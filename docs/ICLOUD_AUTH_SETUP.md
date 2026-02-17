# iCloud Auth Setup

**Connect Your iCloud Contacts**

This guide will help you connect the application to your iCloud Contacts so it can read them.

## Setup Overview (Takes about 5 minutes)

You'll need to:
1. Generate a special app password from Apple
2. Add your email and password to your app's settings file

This is much simpler than Google! Let's get started.

## Step 1: Generate an App-Specific Password

Apple requires you to create a special password just for this app (not your main Apple ID password). This keeps your main password secure.

### 1.1 Go to Apple ID Settings

1. Open [appleid.apple.com](https://appleid.apple.com/) in your web browser
2. Sign in with your Apple ID (your iCloud email and password)

### 1.2 Navigate to Security Section

1. Once signed in, you'll see several sections on the page
2. Find and click on the **"Security"** section
3. Scroll down to find **"App-Specific Passwords"**

### 1.3 Create the Password

1. Click **"Generate Password"** or the **"+"** button
2. Enter a label so you remember what it's for (e.g., "Contacts Sync App")
3. Click **"Create"**
4. Apple will show you a password that looks like: `xxxx-xxxx-xxxx-xxxx`
5. **Copy this password immediately** - you won't be able to see it again!

**Important:** This password is different from your regular Apple ID password. You'll only use it for this app.

## Step 2: Add Your iCloud Details to the App

Now you'll add your iCloud email and the special password to your app's settings.

### 2.1 Open Your Settings File

Open your `docker-compose.yml` file in any text editor.

### 2.2 Add Your iCloud Details

Find the `environment:` section and add these two lines:

```yaml
environment:
  ICLOUD_USERNAME: "your-email@icloud.com"
  ICLOUD_APP_PASSWORD: "xxxx-xxxx-xxxx-xxxx"
```

Replace the values with:
- **ICLOUD_USERNAME**: Your iCloud email address (the one you use to sign into Apple)
- **ICLOUD_APP_PASSWORD**: The special password you just generated (with the dashes)

**Example of what it should look like:**

```yaml
services:
  contacts-app:
    image: your-app-image
    environment:
      ICLOUD_USERNAME: "john.smith@icloud.com"
      ICLOUD_APP_PASSWORD: "abcd-efgh-ijkl-mnop"
      # ... other settings
```

### 2.3 Save the File

Save your `docker-compose.yml` file.

## Step 3: Start the Application

You're all set! Start the application by running:

```bash
docker-compose up -d
```

The application will now be able to access your iCloud Contacts.

## Understanding How This Works

**What you just set up:**
- You created a special password that only this app can use
- The app uses this password to connect to your iCloud contacts
- The app can only **read** your contacts - it cannot change or delete them
- Your main Apple ID password remains private and secure

**Security:**
- Your iCloud email and app password are stored in your `docker-compose.yml` file
- The app can only read contacts, nothing else
- You can delete this app password anytime from [Apple ID Settings](https://appleid.apple.com/)
- If you delete the password, the app will stop working until you create a new one

## Common Issues and Solutions

### Issue: "Authentication failed" or "401 Unauthorized" error

**Solution:** Your app password may be wrong or expired. Create a new one:
1. Go to [appleid.apple.com](https://appleid.apple.com/)
2. Navigate to **Security** → **App-Specific Passwords**
3. Delete the old password for this app (if it exists)
4. Generate a new password
5. Update the `ICLOUD_APP_PASSWORD` value in your `docker-compose.yml` file
6. Restart: `docker-compose restart`

### Issue: Can't find "App-Specific Passwords" option

**Solution:** You need to have two-factor authentication enabled on your Apple ID:
1. Go to [appleid.apple.com](https://appleid.apple.com/)
2. Navigate to **Security** section
3. Turn on **Two-Factor Authentication** if it's not already on
4. Follow Apple's instructions to set it up
5. Once enabled, you'll see the "App-Specific Passwords" option

### Issue: "No contacts found" or contacts not syncing

**Solution:** Check the following:
1. Make sure your `ICLOUD_USERNAME` is correct (it should be your full iCloud email)
2. Make sure you copied the entire app password including all four groups (xxxx-xxxx-xxxx-xxxx)
3. Check that both values are properly in quotes in the `docker-compose.yml` file
4. Restart the app: `docker-compose restart`

### Issue: App password was accidentally lost

**Solution:** No problem! Just create a new one:
1. Go to [appleid.apple.com](https://appleid.apple.com/)
2. Generate a new app-specific password
3. Update your `docker-compose.yml` file with the new password
4. Restart the app

## Security Best Practices

✅ **Safe:**
- App passwords only give access to specific services (in this case, contacts)
- Your main Apple ID password stays private
- You can create and delete app passwords anytime
- Each app password can be labeled so you know what it's for

⚠️ **Important:**
- Keep your `docker-compose.yml` file secure - it contains your access details
- Never share your `docker-compose.yml` file with these values
- Never upload it to GitHub or other public websites with these details
- Each app should have its own unique app password (don't reuse them)

## Managing Your App Passwords

To see or delete your app passwords:

1. Go to [appleid.apple.com](https://appleid.apple.com/)
2. Sign in and navigate to **Security**
3. Click on **App-Specific Passwords**
4. You'll see a list of all your app passwords with their labels
5. Click the **"X"** or **"Delete"** button next to any password to remove it

After deleting a password, any app using that password will stop working until you generate a new one.

## What If I Use a Different Email Provider?

This guide is specifically for iCloud contacts (contacts stored in your Apple account).

If your email ends with:
- **@icloud.com** - This guide is for you! ✅
- **@me.com** - This guide is for you! ✅ (older iCloud email)
- **@mac.com** - This guide is for you! ✅ (older iCloud email)
- **@gmail.com** or others - This is not iCloud. You'll need to use the Google Auth setup instead.

All Apple IDs use the same contacts system, regardless of which email domain you have.
