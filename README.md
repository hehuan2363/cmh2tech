# CMH2.tech Landing Page

AI & Automation consulting website for small to medium businesses.

## Quick Deploy to GitHub Pages (Free Hosting)

### Step 1: Create GitHub Repository

```bash
cd /home/hehua/RepoClaudeCode/CMH2Tech
git init
git add .
git commit -m "Initial landing page"
```

### Step 2: Push to GitHub

1. Go to https://github.com/new
2. Create a repository named `cmh2tech` (or any name)
3. Run these commands:

```bash
git remote add origin https://github.com/hehuan2363/cmh2tech.git
git branch -M main
git push -u origin main
```

### Step 3: Enable GitHub Pages

1. Go to your repo on GitHub
2. Click **Settings** > **Pages**
3. Under "Source", select **main** branch and **/ (root)** folder
4. Click **Save**

Your site will be live at: `https://hehuan2363.github.io/cmh2tech/`

### Step 4: Connect Custom Domain (cmh2.tech)

1. In GitHub Pages settings, add `cmh2.tech` as custom domain
2. In your domain registrar (where you bought cmh2.tech), add these DNS records:

**For apex domain (cmh2.tech):**
```
Type: A
Host: @
Value: 185.199.108.153
       185.199.109.153
       185.199.110.153
       185.199.111.153
```

**For www subdomain:**
```
Type: CNAME
Host: www
Value: hehuan2363.github.io
```

3. Wait 15-30 minutes for DNS propagation
4. Check "Enforce HTTPS" in GitHub Pages settings

## Things to Customize

Before going live, update these in `index.html`:

1. **Calendly link** (line ~290): Replace `https://calendly.com/cmh2tech/discovery` with your actual Calendly URL
2. **Email address**: Replace `huan@cmh2.tech` with your actual email
3. **Profile photo**: Replace the "H" avatar with your actual photo
4. **Pricing**: Adjust service pricing to match your rates

## Optional: Add Professional Photo

Replace the avatar section (around line 245) with:

```html
<img src="your-photo.jpg" alt="Huan He" class="w-16 h-16 rounded-full object-cover">
```

## Local Preview

Just open `index.html` in your browser:

```bash
open index.html  # macOS
xdg-open index.html  # Linux
```

Or use a simple server:

```bash
python3 -m http.server 8000
# Then visit http://localhost:8000
```
