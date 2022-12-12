module.exports = {
  title: 'openPYPE',
  tagline: 'Pipeline with support, for studios and remote teams.',
  url: 'http://openpype.io/',
  baseUrl: '/',
  organizationName: 'Orbi Tools s.r.o',
  projectName: 'openPype',
  favicon: 'img/favicon/favicon.ico',
  onBrokenLinks: 'ignore',
  customFields: {
  },
  presets: [
    [
      '@docusaurus/preset-classic', {
        docs: {
          sidebarPath: require.resolve('./sidebars.js'),
        },
        theme: {
          customCss: require.resolve('./src/css/custom.css')
        },
        gtag: {
        trackingID: 'G-DTKXMFENFY',
        // Optional fields.
        anonymizeIP: false, // Should IPs be anonymized?
      }
      }
    ],
    
  ],
  themeConfig: {
    colorMode: {
      // "light" | "dark"
      defaultMode: 'light',

      // Hides the switch in the navbar
      // Useful if you want to support a single color mode
      disableSwitch: true
    },
    
    navbar: {
      style: 'dark',
      title: 'openPYPE',
      logo: {
        src: 'img/logos/splash_main.svg'
      },
      items: [
        {
          to: '/features',
          label: 'Features',
          position: 'left'
        }, {
          to: 'docs/artist_getting_started',
          label: 'User Docs',
          position: 'left'
        },
        {
          to: 'docs/system_introduction',
          label: 'Admin Docs',
          position: 'left'
        },
        {
          to: 'docs/dev_introduction',
          label: 'Dev Docs',
          position: 'left'
        },
      ]
    },

  },
}
{}