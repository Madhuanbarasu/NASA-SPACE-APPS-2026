
File:            aareadme.txt
Creation Date:   2006-08-04 (NJB)
Revised:         2008-03-18 (NJB)
Revised:         2021-06-25 (NJB)
Revised:         2022-09-30 (NJB)
Revised:         2023-06-17 (BVS)
Revised:         2025-04-16 (NJB)
Authors:         Nat Bachman, Boris Semenov (JPL/NAIF)



Contents of path pub/naif/generic_kernels/fk/satellites
=======================================================

The text kernels discussed here

   moon_de440_250416.tf
   moon_080317.tf
   moon_071218.tf
   moon_assoc_me.tf
   moon_assoc_pa.tf
   *nameid*.tf

are unix-style text files.  They are suitable for use
on all unix boxes, including PC/linux and MAC/OSX machines.


Lunar frame kernel (FK)
-----------------------

   DE440 version
   -------------

   This frame kernel contains specifications of lunar reference frames
   realizing the Lunar Principal Axis (PA) and Mean Earth/Polar Axis (ME)
   reference systems:

      moon_de440_250416.tf

   Reference:

   [1]  Ryan S. Park, et al, "The JPL Planetary and Lunar Ephemerides
        DE440 and DE441," The Astronomical Journal, Volume 161, Number 3.
        2021 AJ 161 105.

        URL:

           https://iopscience.iop.org/article/10.3847/1538-3881/abd414/meta

   The reference frames specified by this kernel are associated with
   the lunar libration data provided by JPL's DE440 planetary ephemeris.
   The ME frame is a variant that has been closely aligned with the
   DE421 ME frame. See [1] for details.

   This frame kernel contains extensive documentation; the kernel may
   by viewed with a text editor or web browser.

   The cited frame kernel is to be used with the binary lunar PCK

      moon_pa_de440_200625.bpc

   This PCK is located in the path

      pub/naif/generic_kernels/pck


   DE421 version
   -------------

   This frame kernel contains specifications of lunar reference frames
   realizing the Lunar Principal Axis (PA) and Mean Earth/Polar Axis (ME)
   reference systems:

      moon_080317.tf

   The reference frames specified by this kernel are associated with
   the lunar libration data provided by JPL's DE-421 planetary ephemeris.

   This frame kernel contains extensive documentation; the kernel may
   by viewed with a text editor or web browser.

   The cited frame kernel is to be used with the binary lunar PCK

      moon_pa_de421_1900-2050.bpc

   This PCK is located in the path

      pub/naif/generic_kernels/pck



   Version preceding DE421
   -----------------------


   This frame kernel contains the latest specifications of lunar
   reference frames realizing the Lunar Principal Axis (PA) and Mean
   Earth/Polar Axis (ME) reference systems:

      moon_071218.tf

   The reference frames specified by this kernel are associated with
   the lunar libration data provided by JPL's DE-418 planetary ephemeris.

   This frame kernel contains extensive documentation; the kernel may
   by viewed with a text editor or web browser.

   The cited frame kernel is to be used with the binary lunar PCK

      moon_pa_de418_1950-2050.bpc

   This PCK is located in the path

      pub/naif/generic_kernels/pck

   A memo describing the PA to ME frame offset is available in this location.
   The document is named de418_ephemeris_and_lunar_orientation.


Lunar body-fixed frame association kernels
------------------------------------------

   By default, the SPICE system considers the body-fixed reference frame
   associated with the Moon to be the one named IAU_MOON.  This body-frame
   association affects the outputs of the SPICE frame system routines

      CIDFRM
      CNMFRM

   and of the SPICE time conversion and geometry routines

      ET2LST
      ILLUM
      SRFXPT
      SUBPT
      SUBSOL

   Finally, any code that calls these routines to obtain results
   involving lunar body-fixed frames are affected.  Within SPICE, the
   only higher-level system that is affected is the dynamic frame
   system.

   NAIF provides "frame association" kernels that simplify changing the
   body-fixed frame associated with the Moon.  Using FURNSH to load
   either of the kernels named below sets the Moon's body-fixed frame
   to that shown in the right-hand column:

      Kernel name          Lunar body-fixed frame
      -----------          ----------------------
      moon_assoc_me.tf     MOON_ME
      moon_assoc_pa.tf     MOON_PA

   For further information see the in-line comments in the association
   kernels themselves.  Also see the Frames Required Reading section
   titled "Connecting an Object to its Body-fixed Frame."


Satellite NAIF name-ID mapping kernels
--------------------------------------

   The *nameid*.tf FK files provide NAIF name-ID mappings for satellites
   from specific satellite ephemeris SPK files which (satellites) do not
   have name-ID mappings built into the SPICE toolkit. For example, the FK 
   jup344_nameid.tf provides mappings for a subset of satellites from 
   the SPK jup344.bsp.
   

Getting help
============

   SPICE tutorials are available on the NAIF web site:

      http://naif.jpl.nasa.gov/naif/

   The following tutorials may be of particular interest:

      Intro to Kernel Files
      PCK (Planetary cartographic and physical constants)
      FK (Reference frame specifications)

   Also see the following Required Reading documents provided
   with the SPICE Toolkit:

      Frames
      Kernel
      PCK

   Many SPICE kernels contain internal documentation. Text kernels may
   be viewed with a text editor or web browser. Comments in binary
   kernels may be viewed using the SPICE utility COMMNT. Coverage of
   binary PCKs may be viewed using the SPICE utility SPACIT. See the
   COMMNT and SPACIT User's Guides (provided with the SPICE Toolkit)
   for details.
