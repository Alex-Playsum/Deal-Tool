## Playsum Product Feed API Documentation

## Overview

The Playsum Product Feed API provides information about our game catalog and game deals in RSS format. This feed can be used by external sites to showcase Playsum's game offerings and deals. The feed may contain multiple entries for the same game due to regional restrictions and pricing differences.

## Endpoint

| `https://api.playsum.live/v1/shop/products/rss` |
| :---- |

## Response Format

The API returns data in RSS 2.0 format with additional custom elements.

## Channel Information 

The feed contains a \<channel\> element with the following sub-elements:

* title: The title of the feed  
* description: A brief description of the feed  
* link: URL of the Playsum Games Store  
* generator: Information about the feed generator  
* lastBuildDate: Date and time when the feed was last updated  
* atom:link: Self-referential link to the feed  
* language: Language code for the feed content

## Product Information

Each product is represented by an \<item\> element within the channel. The \<item\> contains the following sub-elements:

| Element | Description | Example |
| ----- | ----- | ----- |
| title | Name of the game | G.I. Joe: Wrath of Cobra |
| link | URL to the product page | [https://store.playsum.live/product/5f42d226-29e0-4d02-aec4-9aba62fc3eb1/g-i-joe-wrath-of-cobra](https://store.playsum.live/product/5f42d226-29e0-4d02-aec4-9aba62fc3eb1/g-i-joe-wrath-of-cobra) |
| guid | Unique identifier for the product (same as link) | [https://store.playsum.live/product/5f42d226-29e0-4d02-aec4-9aba62fc3eb1/g-i-joe-wrath-of-cobra](https://store.playsum.live/product/5f42d226-29e0-4d02-aec4-9aba62fc3eb1/g-i-joe-wrath-of-cobra) |
| sku | Stock Keeping Unit (unique for each regional variant) | 758514c7-5764-42c7-a505-be4d8e117088 |
| cover\_image | URL of the product's cover image | https://cdn.playsum.live/images/products/758514c7-5764-42c7-a505-be4d8e117088/packshot.jpeg |
| operatingSystems | Is a string of operating systems divided by comma that the game supports | WINDOWS |
| keyProvider | Platform providing the game key | Steam Works |
| whitelistedCountries | A string of countries divided by comma where the product is available | IN,TR |
| blacklistedCountries | A string of countries divided by comma where the product is not available | (empty if none) |
| whitelistedCountry | Replaced by whitelistedCountries and will be deprecated August 6th 2025\. **Do not use.** | Now deprecated |
| currency | Currency for pricing | USD |
| discountPrice | Current discounted price | 11.24 |
| discountPercentage | Current discount percentage (blank if no discount) | 20 |
| discountStartDate | Discount start time (Unix timestamp, ms; blank if none) | 1748881800000 |
| discountEndDate | Discount end time (Unix timestamp, ms; blank if none) | 1750091340000 |
| originalPrice | Original price before discount | 12.49 |

## Regional Variants

The feed may contain multiple entries for the same game due to regional restrictions and pricing differences. Each variant will have:

1. The same title, link, and guid.  
2. A unique sku for each regional variant.  
3. Different whitelistedCountries values indicating the regions where the variant is available.  
4. Potentially different discountPrice and originalPrice values.

## Usage Notes

1. The whitelistedCountries and blacklistedCountries elements use ISO 3166-1 alpha-2 country codes.  
2. The currency element uses ISO 4217 currency codes.  
3. Prices are provided in the currency specified in the currency element.  
4. The operatingSystems element may contain multiple values for cross-platform games.  
5. The guid element uses the isPermaLink attribute set to "true", indicating that the GUID is also a permanent URL for the item.  
6. If a product is not on discount, the discountPrice, discountPercentage, discountStartDate, and discountEndDate fields will be empty.  
7. Discount start and end times are provided as Unix timestamps in milliseconds.

## Currency Support

## The Playsum Games Store currently supports the following currencies:

1. ## USD (United States Dollar)

2. ## EUR (Euro)

3. CAD (Canadian Dollar)  
4. AUD (Australian Dollar)

## Currency allocation is determined as follows:

* ## EUR: Used for all countries that have Euro as their official currency. As well as for Czech Republic, Sweden, and Poland.

* ## USD: Used for all countries that have US Dollar as their official currency.

* CAD: Used for Canada.  
* AUD: Used for Australia.  
* GBP: Used for Great Britain.

* ## Default to USD: For all other countries not falling into the above categories, prices are shown in USD.

## Examples 

Here's an example of how the same game might appear with different regional variants and curriences:

| `<item> <title> <![CDATA[ Shapez 2 ]]> </title> <link>https://store.playsum.live/product/04ab1343-cc71-4511-be3c-26bee95ea40d/shapez-2</link> <guid isPermaLink="true">https://store.playsum.live/product/04ab1343-cc71-4511-be3c-26bee95ea40d/shapez-2</guid> <sku>de3c0396-b8d3-4499-a23b-f20880234da2</sku> <cover_image>https://cdn.playsum.live/images/products/0c509cf1-4c63-473f-903e-f41b4cdccb2d/packshot.jpeg</cover_image> <operatingSystems>LINUX,WINDOWS,MAC</operatingSystems> <keyProvider>Steam Works</keyProvider> <whitelistedCountries>AT,AU,BE,CA,CH,CY,DE,EE,ES,FI,FR,GB,GR,HR,IE,IL,IT,LT,LU,LV,MT,NL,NO,NZ,PT,SI,SK,US</whitelistedCountries> <blacklistedCountries>CN,JP,MO</blacklistedCountries> <currency>USD</currency> <discountPrice>17.49</discountPrice> <discountPercentage>30</discountPercentage> <discountStartDate>1748822460000</discountStartDate> <discountEndDate>1750118399000</discountEndDate> <originalPrice>24.99</originalPrice> </item> <item> <title> <![CDATA[ Shapez 2 ]]> </title> <link>https://store.playsum.live/product/04ab1343-cc71-4511-be3c-26bee95ea40d/shapez-2</link> <guid isPermaLink="true">https://store.playsum.live/product/04ab1343-cc71-4511-be3c-26bee95ea40d/shapez-2</guid> <sku>de3c0396-b8d3-4499-a23b-f20880234da2</sku> <cover_image>https://cdn.playsum.live/images/products/0c509cf1-4c63-473f-903e-f41b4cdccb2d/packshot.jpeg</cover_image> <operatingSystems>LINUX,WINDOWS,MAC</operatingSystems> <keyProvider>Steam Works</keyProvider> <whitelistedCountries>AT,AU,BE,CA,CH,CY,DE,EE,ES,FI,FR,GB,GR,HR,IE,IL,IT,LT,LU,LV,MT,NL,NO,NZ,PT,SI,SK,US</whitelistedCountries> <blacklistedCountries>CN,JP,MO</blacklistedCountries> <currency>EUR</currency> <discountPrice>16.29</discountPrice> <discountPercentage>32</discountPercentage> <discountStartDate>1748822460000</discountStartDate> <discountEndDate>1750118399000</discountEndDate> <originalPrice>23.99</originalPrice> </item> <item> <title> <![CDATA[ Shapez 2 ]]> </title> <link>https://store.playsum.live/product/04ab1343-cc71-4511-be3c-26bee95ea40d/shapez-2</link> <guid isPermaLink="true">https://store.playsum.live/product/04ab1343-cc71-4511-be3c-26bee95ea40d/shapez-2</guid> <sku>0c509cf1-4c63-473f-903e-f41b4cdccb2d</sku> <cover_image>https://cdn.playsum.live/images/products/0c509cf1-4c63-473f-903e-f41b4cdccb2d/packshot.jpeg</cover_image> <operatingSystems>LINUX,WINDOWS,MAC</operatingSystems> <keyProvider>Steam Works</keyProvider> <whitelistedCountries>AE,CL,CR,KR,KW,MX,PE,PL,QA,SA,SG,UY</whitelistedCountries> <blacklistedCountries>CN,JP,MO</blacklistedCountries> <currency>USD</currency> <discountPrice>18.74</discountPrice> <discountPercentage>25</discountPercentage> <discountStartDate>1748822460000</discountStartDate> <discountEndDate>1750118399000</discountEndDate> <originalPrice>24.99</originalPrice> </item>` |
| :---- |

Here's an example of how a game without an active discount would appear.

| `<item> <title> <![CDATA[ Clair Obscur: Expedition 33 ]]> </title> <link>https://store.playsum.live/product/f2d66472-06f6-494a-92ad-c756608ade5f/clair-obscur-expedition-33</link> <guid isPermaLink="true">https://store.playsum.live/product/f2d66472-06f6-494a-92ad-c756608ade5f/clair-obscur-expedition-33</guid> <sku>4e99a8c1-e03d-4381-9b5a-e3253dd01c4e</sku> <cover_image>https://cdn.playsum.live/images/products/e26bf587-d25f-4440-acae-4f7fc7560f73/packshot.jpeg</cover_image> <operatingSystems>WINDOWS</operatingSystems> <keyProvider>Steam Works</keyProvider> <whitelistedCountries>BD,IN,PK,TR</whitelistedCountries> <blacklistedCountries/> <currency>USD</currency> <discountPrice/> <discountPercentage/> <discountStartDate/> <discountEndDate/> <originalPrice>34.99</originalPrice> </item>` |
| :---- |

##  Access and Authentication

To access the Playsum Product Feed API, you must provide us with the IP addresses that will be used to make requests to the feed. This security measure ensures only authorized users can access the data. Please contact [partners@playsum.live](mailto:partners@playsum.live) with the list of IP addresses that need access. Once your IPs are whitelisted, you'll receive a confirmation email.