# Google Auth Setup

**Connect Your Google Contacts**

This guide will help you connect the application to your Google Contacts so it can read them.


## Setup Overview (Takes about 10-15 minutes)

You'll need to:
1. Create a project in Google's setup page
2. Download a file with your connection details
3. Generate a special code that lets the app access your contacts
4. Add these details to your app's settings file

Don't worry - we'll walk through each step!

## Step 1: Set Up Your Google Project

### 1.1 Create a New Project

1. Open [Google Cloud Console](https://console.cloud.google.com/) (this is Google's setup page)
2. At the top of the page, click on the project dropdown (next to "Google Cloud")
3. Click **"NEW PROJECT"**
4. Give it a name like "My Contacts App"
5. Click **"CREATE"**

### 1.2 Enable Access to Google Contacts

1. In the left menu, go to **"APIs & Services"** → **"Library"**
2. In the search box, type **"Google People API"**
3. Click on **"Google People API"** from the results
4. Click the blue **"ENABLE"** button

### 1.3 Create Your Connection Settings

1. In the left menu, go to **"APIs & Services"** → **"Credentials"**
2. Click **"+ CREATE CREDENTIALS"** at the top
3. Select **"OAuth client ID"**
4. If prompted to set up the consent screen:
   - Choose **"External"**
   - Fill in the app name (e.g., "My Contacts App")
   - Add your email address
   - Click **"SAVE AND CONTINUE"** through the remaining screens
5. Back on the credentials page, select **"Desktop app"** as the application type
6. Give it a name like "Desktop Client"
7. Click **"CREATE"**

### 1.4 Download Your Connection File

1. A popup will appear showing your connection details
2. Click **"DOWNLOAD JSON"**
3. Save this file - you'll need it in the next step
4. Rename it to `credentials.json` (if it has a different name)

## Step 2: Generate Your Access Code

Now you need to generate a special code that allows the application to access your contacts.

### 2.1 Find Your Connection Details

1. Open the `credentials.json` file you downloaded in Step 1 with any text editor (Notepad, TextEdit, etc.)
2. Find and copy these two values:
   - `client_id` (looks like: `123456789-abc...xyz.apps.googleusercontent.com`)
   - `client_secret` (looks like: `GOCSPX-...`)

### 2.2 Set Up Google's Testing Page

1. Go to [Google's Testing Page](https://developers.google.com/oauthplayground/)
2. Click the **gear icon** (⚙️) in the top right corner
3. Check the box **"Use your own OAuth credentials"**
4. Paste your **client_id** and **client_secret** from step 2.1
5. Click **"Close"**

### 2.3 Give Permission and Get Your Code

1. In the left panel, scroll down and expand **"Google People API v1"**
2. Check the box next to **`https://www.googleapis.com/auth/contacts.readonly`**
3. Click the blue **"Authorize APIs"** button at the bottom
4. Google will ask you to sign in and grant permission - click **"Allow"**
5. You'll be redirected back to the testing page
6. Click **"Exchange authorization code for tokens"**
7. On the right side, you'll see a section called **"Refresh token"** - copy this value

You now have all three values you need:
- **client_id** (from credentials.json)
- **client_secret** (from credentials.json)
- **Refresh token** (from Google's testing page)

## Step 3: Add Your Connection Details to the App

Now you need to add these three values to your app's settings file.

### 3.1 Open Your Settings File

Open your `docker-compose.yml` file in any text editor.

### 3.2 Add Your Connection Details

Find the `environment:` section for the application service and add these three lines:

```yaml
environment:
  GOOGLE_CLIENT_ID: "your-client-id-here.apps.googleusercontent.com"
  GOOGLE_CLIENT_SECRET: "GOCSPX-your-client-secret-here"
  GOOGLE_REFRESH_TOKEN: "1//your-refresh-token-here"
```

Replace the values with:
- **GOOGLE_CLIENT_ID**: The `client_id` from your `credentials.json` file
- **GOOGLE_CLIENT_SECRET**: The `client_secret` from your `credentials.json` file
- **GOOGLE_REFRESH_TOKEN**: The refresh token you got from Google's testing page in Step 2.3

**Example of what it should look like:**

```yaml
services:
  contacts-app:
    image: your-app-image
    environment:
      GOOGLE_CLIENT_ID: "123456789-abcdefghijklmnop.apps.googleusercontent.com"
      GOOGLE_CLIENT_SECRET: "GOCSPX-Ab1Cd2Ef3Gh4Ij5"
      GOOGLE_REFRESH_TOKEN: "1//0abcdefghijklmnopqrstuvwxyz"
      # ... other settings
```

### 3.3 Save the File

## Step 4: Start the Application

Now you're ready! Start the application by running:

```bash
docker-compose up -d
```

The application will now be able to access your Google Contacts.

## Understanding How This Works

**What you just set up:**
- You gave the application permission to read your Google Contacts
- The application uses a "refresh token" (the special code) to maintain this permission
- This code doesn't expire unless you manually remove access
- The application can only **read** your contacts - it cannot change or delete them

**Security:**
- Your connection details are stored in your `docker-compose.yml` file
- The application can only read contacts, nothing else
- You can remove access anytime from your [Google Account Settings](https://myaccount.google.com/permissions)

## Common Issues and Solutions

### Issue: "Invalid refresh token" error

**Solution:** Your code may have expired or been removed. Generate a new one:
1. Go back to [Google's Testing Page](https://developers.google.com/oauthplayground/) and repeat Step 2
2. Copy the new `GOOGLE_REFRESH_TOKEN` value
3. Replace the old value in your `docker-compose.yml` file
4. Restart: `docker-compose restart`

### Issue: "Client ID not found" error

**Solution:** Check that all three connection details are in your `docker-compose.yml` file:
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REFRESH_TOKEN`

Make sure there are no typos and the values are properly in quotes.

### Issue: Google's testing page doesn't show my connection details

**Solution:** Make sure you opened the `credentials.json` file correctly. The file should look like this:

```json
{
  "installed": {
    "client_id": "123456789-abc...xyz.apps.googleusercontent.com",
    "client_secret": "GOCSPX-...",
    ...
  }
}
```

Copy the values between the quotes.

## Security Best Practices

✅ **Safe:**
- The code only grants **read-only** access to your contacts
- The code is specific to your Google account
- You can remove access anytime from [Google Account Settings](https://myaccount.google.com/permissions)

⚠️ **Important:**
- Keep your `docker-compose.yml` file secure - it contains your access details
- Never share your `docker-compose.yml` file with these values
- Never upload it to GitHub or other public websites with these details
- For advanced users: consider using Docker secrets or other secure storage methods

## Removing Access

If you want to remove the application's access to your Google Contacts:

1. Go to [Google Account Permissions](https://myaccount.google.com/permissions)
2. Find your app in the list (e.g., "My Contacts App")
3. Click on it and select **"Remove Access"**

After removing access, you'll need to go through this setup again if you want to reconnect.
