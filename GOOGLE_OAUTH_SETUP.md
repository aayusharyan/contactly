# Google OAuth Setup Guide

**Connect your Google Contacts to this application**

This guide will help you set up Google OAuth so the application can read your Google Contacts.


## Setup Overview (Takes about 10-15 minutes)

You'll need to:
1. Set up a project in Google Cloud Console
2. Download a credentials file
3. Run a setup tool to get your access token
4. Copy some values into a configuration file

Don't worry - we'll walk through each step!

## Step 1: Set Up Google Cloud Project

### 1.1 Create a New Project

1. Open [Google Cloud Console](https://console.cloud.google.com/)
2. At the top of the page, click on the project dropdown (next to "Google Cloud")
3. Click **"NEW PROJECT"**
4. Give it a name like "Contactly Instance"
5. Click **"CREATE"**

### 1.2 Enable the Google People API

1. In the left menu, go to **"APIs & Services"** → **"Library"**
2. In the search box, type **"Google People API"**
3. Click on **"Google People API"** from the results
4. Click the blue **"ENABLE"** button

### 1.3 Create OAuth Credentials

1. In the left menu, go to **"APIs & Services"** → **"Credentials"**
2. Click **"+ CREATE CREDENTIALS"** at the top
3. Select **"OAuth client ID"**
4. If prompted to configure the OAuth consent screen:
   - Choose **"External"**
   - Fill in the app name (e.g., "Contactly Instance")
   - Add your email address
   - Click **"SAVE AND CONTINUE"** through the remaining screens
5. Back on the credentials page, select **"Desktop app"** as the application type
6. Give it a name like "Desktop Client"
7. Click **"CREATE"**

### 1.4 Download Your Credentials File

1. A popup will appear showing your Client ID and Client Secret
2. Click **"DOWNLOAD JSON"**
3. Save this file - you'll need it in the next step
4. Rename it to `credentials.json` (if it has a different name)

## Step 2: Get Your Access Token

Now you need to generate a special token that allows the application to access your contacts.

### 2.1 Get Your Client ID and Secret

1. Open the `credentials.json` file you downloaded in Step 1 with any text editor (Notepad, TextEdit, etc.)
2. Find and copy these two values:
   - `client_id` (looks like: `123456789-abc...xyz.apps.googleusercontent.com`)
   - `client_secret` (looks like: `GOCSPX-...`)

### 2.2 Configure OAuth Playground

1. Go to [Google OAuth 2.0 Playground](https://developers.google.com/oauthplayground/)
2. Click the **gear icon** (⚙️) in the top right corner
3. Check the box **"Use your own OAuth credentials"**
4. Paste your **Client ID** and **Client Secret** from step 2.1
5. Click **"Close"**

### 2.3 Authorize and Get Token

1. In the left panel, scroll down and expand **"Google People API v1"**
2. Check the box next to **`https://www.googleapis.com/auth/contacts.readonly`**
3. Click the blue **"Authorize APIs"** button at the bottom
4. Google will ask you to sign in and grant permission - click **"Allow"**
5. You'll be redirected back to the Playground
6. Click **"Exchange authorization code for tokens"**
7. On the right side, you'll see a section called **"Refresh token"** - copy this value

You now have all three values you need:
- **Client ID** (from credentials.json)
- **Client Secret** (from credentials.json)  
- **Refresh Token** (from OAuth Playground)

## Step 3: Add Credentials to Your Docker Compose

Now you need to add these three values to your Docker Compose configuration.

### 3.1 Open Your Docker Compose File

Open your `docker-compose.yml` file in any text editor.

### 3.2 Add the Environment Variables

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
- **GOOGLE_REFRESH_TOKEN**: The refresh token you got from OAuth Playground in Step 2.3

**Example of what it should look like:**

```yaml
services:
  contacts-app:
    image: your-app-image
    environment:
      GOOGLE_CLIENT_ID: "123456789-abcdefghijklmnop.apps.googleusercontent.com"
      GOOGLE_CLIENT_SECRET: "GOCSPX-Ab1Cd2Ef3Gh4Ij5"
      GOOGLE_REFRESH_TOKEN: "1//0abcdefghijklmnopqrstuvwxyz"
      # ... other environment variables
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
- The application uses a "refresh token" to maintain this permission
- This token doesn't expire unless you manually revoke it
- The application only has **read-only** access - it cannot modify or delete your contacts

**Security:**
- Your credentials are stored in your `docker-compose.yml` file
- The application can only read contacts, nothing else
- You can revoke access anytime from your [Google Account Settings](https://myaccount.google.com/permissions)

## Common Issues and Solutions

### Issue: "Invalid refresh token" error

**Solution:** Your token may have expired or been revoked. Generate a new one:
1. Go back to [Google OAuth Playground](https://developers.google.com/oauthplayground/) and repeat Step 2
2. Copy the new `GOOGLE_REFRESH_TOKEN` value
3. Replace the old value in your `docker-compose.yml` file
4. Restart: `docker-compose restart`

### Issue: "Client ID not found" error

**Solution:** Check that all three environment variables are in your `docker-compose.yml` file:
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REFRESH_TOKEN`

Make sure there are no typos and the values are properly quoted.

### Issue: OAuth Playground doesn't show credentials.json values

**Solution:** Make sure you opened the `credentials.json` file correctly. The file is in JSON format and should look like this:

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
- The token only grants **read-only** access to your contacts
- The token is specific to your Google account
- You can revoke access anytime from [Google Account Settings](https://myaccount.google.com/permissions)

⚠️ **Important:**
- Keep your `docker-compose.yml` file secure - it contains your access credentials
- Never share your `docker-compose.yml` file with these values
- Never upload it to GitHub or other public places with these credentials
- Consider using Docker secrets or external configuration management for production environments

## Revoking Access

If you want to revoke the application's access to your Google Contacts:

1. Go to [Google Account Permissions](https://myaccount.google.com/permissions)
2. Find your app in the list (e.g., "My Contacts App")
3. Click on it and select **"Remove Access"**

After revoking, you'll need to go through the setup again if you want to reconnect.
