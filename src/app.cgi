#!/usr/bin/perl
#
#indx#	app.cgi - VERY primative AI for medical diagnostics
#@HDR@	$Id$
#@HDR@
#@HDR@	Copyright (c) 2024-2026 Christopher Caldwell (Christopher.M.Caldwell0@gmail.com)
#@HDR@
#@HDR@	Permission is hereby granted, free of charge, to any person
#@HDR@	obtaining a copy of this software and associated documentation
#@HDR@	files (the "Software"), to deal in the Software without
#@HDR@	restriction, including without limitation the rights to use,
#@HDR@	copy, modify, merge, publish, distribute, sublicense, and/or
#@HDR@	sell copies of the Software, and to permit persons to whom
#@HDR@	the Software is furnished to do so, subject to the following
#@HDR@	conditions:
#@HDR@	
#@HDR@	The above copyright notice and this permission notice shall be
#@HDR@	included in all copies or substantial portions of the Software.
#@HDR@	
#@HDR@	THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY
#@HDR@	KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
#@HDR@	WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE
#@HDR@	AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
#@HDR@	HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
#@HDR@	WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#@HDR@	FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
#@HDR@	OTHER DEALINGS IN THE SOFTWARE.
#
#hist#	2026-02-19 - Christopher.M.Caldwell0@gmail.com - Created
########################################################################
#doc#	app.cgi - VERY primative AI for medical diagnostics
########################################################################

use strict;
use lib "/usr/local/lib/perl";
use cpi_setup qw(setup);
use cpi_db qw(dbadd dbarr dbdel dbget dbpop dbput dbwrite);
use cpi_translate qw(xprint);
use cpi_cgi qw(safe_html show_vars);
use cpi_user qw(in_group logout_select);
use cpi_file qw(cleanup fatal);
use cpi_lock qw( lock_file unlock_file );
use cpi_vars;

&setup(Qpreset_language=>"en");

my $DEBUG = 1;
$| = 1;

my $THRESHHOLD = 0.1;

#########################################################################
#	Variable declarations.						#
#########################################################################

my $NOTFOUND		= "#c0a0a0";
my @OBJECT_TYPES	= ("result","test","suite","solution","case");
my %OBJ_INFO	=
    (
    "result"	=>  {
		    base	=>	"#c080c0",
		    rows	=>	[ "#d060e0", "#b090b0" ],
		    table	=>	\&table_result
		    },
    "test"	=>  {
		    base	=>	"#c08080",
		    rows	=>	[ "#d06060", "#b09090" ],
		    table	=>	\&table_test,
		    display	=>	\&display_test,
		    update	=>	\&update_test,
		    download	=>	\&download_test
		    },
    "suite"	=>  {
		    base	=>	"#408080",
		    rows	=>	[ "#d0d060", "#b06090" ],
		    display	=>	\&display_suite,
		    table	=>	\&table_suite,
		    download	=>	\&download_suite
		    },
    "testsuite"	=>  {
		    base	=>	"#408080"
		    },
    "solution"	=>  {
		    base	=>	"#40a040",
		    rows	=>	[ "#20b020", "#509050" ],
		    table	=>	\&table_solution,
		    download	=>	\&download_solution
		    },
    "case"	=>  {
		    base	=>	"#40c0c0",
		    rows	=>	[ "#30d0d0", "#50b0b0" ],
		    table	=>	\&table_case,
		    display	=>	\&display_case,
		    update	=>	\&update_case,
		    download	=>	\&download_case
		    },
    "all"	=>  {
		    base	=>	"#707040"
		    }
    );

my @DUMP_EXCLUDE	= ( "SID", "USER", "current_group", "func" );
my %PARENTS		= ( "result"=>"test", "test"=>"suite" );

my %caller		= ();
my $discipline		= "";
my @problems		= ();
my $RSEP		= ":-";

#########################################################################
#	Turn text into something usable as a variable name.		#
#########################################################################
sub make_token
    {
    my( $tokname ) = @_;
    $tokname =~ s/[^\w]+/_/g;
    $tokname =~ s/^_*//;
    $tokname =~ s/_*$//;
    return $tokname;
    }

#########################################################################
#	Short hand routines for database access.			#
#########################################################################
sub DBDget	{ return &dbget(   $cpi_vars::DB, $discipline, @_	); }
sub DBDput	{ return &dbput(   $cpi_vars::DB, $discipline, @_	); }
sub DBDadd	{ return &dbadd(   $cpi_vars::DB, $discipline, @_	); }
sub DBDdel	{ return &dbdel(   $cpi_vars::DB, $discipline, @_	); }
sub DBDpop	{ return &dbpop(   $cpi_vars::DB			); }
sub DBDwrite	{ return &dbwrite( $cpi_vars::DB			); }
sub DBDgetdef
    {
    my $res = &dbget( $cpi_vars::DB, $discipline, @_ );
    return ( defined($res) ? $res : "" );
    }
sub DBDget0
    {
    my $res = &dbget( $cpi_vars::DB, $discipline, @_ );
    return ( (defined($res) && ($res ne "")) ? $res : 0 );
    }
sub DBDchange
    {
    my( @args ) = @_;
    my $newval = pop( @args );
    my $lastval = &DBDget( @args );
    return 1 if( defined($lastval) && $newval eq $lastval );
    return &DBDput( @args, $newval );
    }

#sub xl {return &COMMON::translate_db($cpi_vars::WRITTEN_IN,$cpi_vars::LANG,$_[0]);}
sub xl { return $_[0]; }

#########################################################################
#	Return HTML for a hidden variable				#
#########################################################################
sub hidden
    {
    my $pstring = "";
    $pstring .= sprintf("<input type=hidden name=%s value=\"%s\">\n",
        shift(@_), shift(@_ ) )
	    while( @_ );
    return $pstring;
    }

my $current_form;
#########################################################################
#	setup_form							#
#########################################################################
sub setup_form
    {
    my( $formname, $funcval, @varvals ) = @_;
    $current_form = $formname;
    push( @varvals, "SID=$cpi_vars::SID", "user=$cpi_vars::USER", "func=$funcval" );
    my $pstring = <<EOF;
<script>
function ${formname}_button( newfunc, newval0, newval1 )
    {
    with( window.document.${formname}form )
        {
	if( typeof(newfunc) != "undefined" ) { func.value = newfunc; }
	if( typeof(newval0) != "undefined" ) { val0.value = newval0;  }
	if( typeof(newval1) != "undefined" ) { val1.value = newval1;  }
	submit();
	}
    }
</script>
<form name=${formname}form method=POST ENCTYPE="multipart/form-data">
EOF
    foreach my $svar ( @varvals )
	{
	if( $svar =~ /(.*?)=(.*)/ )
	    { $pstring .= &hidden($1,$2); }
	else
	    { $pstring .= &hidden($svar,$cpi_vars::FORM{$svar}); }
	}
    return $pstring;
    }

#########################################################################
#	Create a button that invokes the button javascript with the	#
#	specified arguments.						#
#########################################################################
sub button
    {
    my( $title, @values ) = @_;
    return "<input type=button value=\"XL($title)\" " .
        "onClick='${current_form}_button(\"".join('","',@values)."\");'>"
    }

#########################################################################
#	Return the empty string when the arg is undefined.		#
#########################################################################
sub first_defined
    {
    my( @vals ) = @_;
    foreach my $pv ( @vals )
        { return $pv if( defined($pv) && $pv ne "" ); }
    return "";
    }

#########################################################################
#	Return the specified form variable or "" if not set.		#
#########################################################################
sub formdef
    {
    my $res = $cpi_vars::FORM{$_[0]};
    return ( defined($res) ? $res : "" );
    }

#########################################################################
#	Print a footer.							#
#########################################################################
sub footer
    { my $pstring = &setup_form("foot","","val0=","footer=1") . <<EOF1;
<p>
<script>
function do_discipline(t)
    {
    if( t.value != "+" )
        { document.footform.discipline.value = t.value; }
    else
	{ document.footform.discipline.value=prompt("XL(Enter new discipline)"); }
   
    foot_button("goto","dest=search,objtype=case");
    }
</script>
<center><table $cpi_vars::TABLE_TAGS border=1> <tr><th><table width=100%>
<tr><td align=left><center>
<input type=hidden name=discipline value="$discipline">
<select name=discipline_select onChange='do_discipline(this);'>
<option value="">XL(Select discipline)
EOF1
    $pstring .= "<option value=\"+\">XL(Add discipline)\n"
	if( &can_admin() );
    my %selflag = ( $discipline, " selected" );
    foreach my $tempdisc ( sort &dbget($cpi_vars::DB,"Disciplines") )
        {
	$pstring .=
	    "<option value=\"$tempdisc\"$selflag{$tempdisc}>XL($tempdisc)\n";
	}
    $pstring .= "</select>";

    if( $discipline )
	{
	foreach my $objtype ( reverse @OBJECT_TYPES )
	    {
	    my $prettytext = ucfirst( $objtype ) . "s";
	    $pstring.=
		&button( $prettytext,"call","dest=search,objtype=$objtype");
	    }
	    
	$pstring .=
	      &button("Entire database","call","dest=search,objtype=all")
	    . &button("Show database",	"call","dest=show_db")
	    . &button("Text dump",	"download")
	    . &button("Upload",		"upload");
	}
    $pstring .= &logout_select("footform")
	. <<EOF3;
</td></tr></table></th></tr></table></center></form>
EOF3
    &xprint( $pstring );
    }

#########################################################################
#	Print a list of errors with some nice html.			#
#########################################################################
sub show_problems
    {
    my( $msg ) = @_;
    my $pstring = <<EOF1;
<center><table $cpi_vars::TABLE_TAGS border=1>
<tr><th align=left>
<font color=red><font color=white>XL($msg):</font>
EOF1
    $pstring .= "<ul>\n<li><font color=white>"
	. join("</font>\n<li><font color=white>",@problems) .
	"</font>\n</ul>\n" if( @problems );
    $pstring .= <<EOF2;
<center><font color=white>
<input type=button onClick='window.history.back();' value="XL(Go back)">
XL(and correct the entries.)</font></center>
</th></tr></table></center>
EOF2
    return $pstring;
    }

#########################################################################
#	Returns the text based on a result number, or Unspecified.	#
#########################################################################
sub result_text
    {
    my( $r ) = @_;
    my $ret = "Unspecified";
    if( $r >= 0 )
       {
       $ret = &DBDget("result",$_[0],"short");
       $ret = $1 if( $ret =~ /^.*$RSEP(.*)$/ )
       }
    return $ret;
    }

#########################################################################
#	Return indices of an object that matches the specified		#
#	argument in the database by comparing short and long fields.	#
#	Linear search.							#
#########################################################################
sub text_to_db_ind
    {
    my ( $objtype, $l4 ) = @_;
    for( my $objnum=&DBDget0($objtype); $objnum-->0; )
        {
	return $objnum
	    if( &justtext(&DBDgetdef($objtype,$objnum,"short")) eq $l4 );
#	    if( &justtext(&DBDgetdef($objtype,$objnum,"short")) eq $l4
#	    ||  &justtext(&DBDgetdef($objtype,$objnum,"long"))  eq $l4 );
	}
    return "";
    }

#########################################################################
#	Add in or subtract out a solution from a case.			#
#########################################################################
sub add_to_solution_table
    {
    my( $flag, $s, $results ) = @_;
    foreach my $tr (split(/,/,$results))
	{
	my( $t, $r ) = split(/:/,$tr);
	&DBDput("solution",$s,$t,$r,&DBDget0("solution",$s,$t,$r)+$flag);
	&DBDput("solution",$s,$t,"total",&DBDget0("solution",$s,$t,"total")+$flag);
	}
    }

#########################################################################
#	Update result information for a particular case.		#
#########################################################################
sub update_solutions
    {
    my( $objnum, $newsolution, $newresults ) = @_;
    my( $objtype ) = "case";

    my $oldsolution = &DBDgetdef($objtype,$objnum,"solution");
    my $oldresults = &DBDgetdef($objtype,$objnum,"results");
    if( $oldresults ne $newresults || $oldsolution ne $newsolution )
	{
	&add_to_solution_table(-1, $oldsolution, $oldresults)
	    if($oldsolution ne "");
	&add_to_solution_table( 1, $newsolution, $newresults)
	    if($newsolution ne "");
	&DBDchange($objtype,$objnum,"results",$newresults);
	&DBDchange($objtype,$objnum,"solution",$newsolution);
	if( $oldsolution ne $newsolution )
	    {
	    &DBDdel( "solution", $oldsolution, "cases", $objnum )
	        if( $oldsolution ne "" );
	    &DBDadd( "solution", $newsolution, "cases", $objnum )
	        if( $newsolution ne "" );
	    }
	}
    &DBDchange($objtype,$objnum,"owner",$cpi_vars::USER);
    }

#########################################################################
#	Called by both func_update and func_select, since creating an	#
#	object implicitly selects it.					#
#########################################################################
sub actual_select
    {
    my( $write_db ) = @_;
    my @stack = split(/\|/,&formdef("stack"));
    my %curcaller = map { split(/=/) } split(/,/,$stack[$#stack]);
    #%caller = map { split(/=/) } split(/,/,&formdef("val0"));
    my %callercaller = map { split(/=/) } split(/,/,$stack[$#stack-1]);
    &DBDwrite() if( $write_db );
    if( $callercaller{objtype} eq "test" && $curcaller{objtype} eq "result" )
        {
	my $c = $curcaller{objnum};
	my $p = $callercaller{objnum};
	my @associated = &DBDgetdef("test",$p,"associated");
	unless( grep( $_ eq $curcaller{objnum}, @associated ) )
	    {
	    &DBDadd("test",$p,"associated",$c);
	    &DBDadd("test",$p,"enabled",$c);
	    }
	}
    elsif( $callercaller{objtype} eq "suite" && $curcaller{objtype} eq "test" )
        {
	my $c = $curcaller{objnum};
	my $p = $callercaller{objnum};
	my @associated = &DBDgetdef("suite",$p,"associated");
	unless( grep( $_ eq $curcaller{objnum}, @associated ) )
	    {
	    &DBDadd("suite",$p,"associated",$c);
	    &DBDadd("suite",$p,"enabled",$c);
	    }
	}
    elsif( $callercaller{objtype} eq "case" )
        {
	my $c = $callercaller{objnum};
	my $newsolution = &DBDgetdef("case",$c,"solution");
	my $newresultstring = &DBDgetdef("case",$c,"results");
	if( $curcaller{objtype} eq "test" || $curcaller{objtype} eq "suite" )
	    {
	    my @resultarray = split(/,/,$newresultstring);
	    foreach my $t (
		( $curcaller{objtype} eq "suite"
		? &DBDget("suite",$curcaller{objnum},"associated")
		: ( $curcaller{objnum} )
		) )
		{
		@resultarray = grep( /^(\d+):/ && $1 != $t, @resultarray );
		push( @resultarray, "${t}:-1" );
		}
	    $newresultstring = join(",",@resultarray);
	    }
	elsif( $curcaller{objtype} eq "solution" )
	    {
	    $newsolution = $curcaller{objnum};
	    }
	&update_solutions($c,$newsolution,$newresultstring);
	}
    &DBDpop() if( $write_db );
    }

#########################################################################
#	Return just essense of text for comparison sake.		#
#########################################################################
sub justtext
    {
    return lc( &make_token( $_[0] ) );
    }

#########################################################################
#	Code specific to updating a suite.				#
#########################################################################
sub update_suite
    {
    my( $objnum ) = @_;
    my $objtype = "suite";
    &DBDchange($objtype,$objnum,"enabled",
	&dbarr( split(/,/,$cpi_vars::FORM{enabled}) ) );
    }

#########################################################################
#	Code specific to updating a test.				#
#########################################################################
sub update_test
    {
    my( $objnum ) = @_;
    my $objtype = "test";
    &DBDchange($objtype,$objnum,"enabled",
	&dbarr( split(/,/,$cpi_vars::FORM{enabled}) ) );
    &DBDchange($objtype,$objnum,"multiple",&formdef("multiple"));
    }

#########################################################################
#	Code specific to updating a case.				#
#########################################################################
sub update_case
    {
    my( $objnum ) = @_;
    my $objtype = "case";
    my $oldsolution = &DBDgetdef($objtype,$objnum,"solution");
    my $newsolution = $oldsolution;
    my $newresultstring = &DBDgetdef($objtype,$objnum,"results");
    my @resultlist = split(/,/,$newresultstring);
    foreach my $chcmd ( split(/,/,&formdef("changeres")) )
	{
	if( $chcmd =~ /^\+(.*):(.*)/ )
	    {
	    @resultlist = grep( ! /^${1}:-1/, @resultlist );
	    push( @resultlist, "${1}:${2}" );
	    }
	elsif( $chcmd =~ /^-(.*)/ )
	    { @resultlist = grep( $_ ne $1, @resultlist ); }
	elsif( $chcmd =~ /(.*):(.*)/ )
	    {
	    my( $t, $r ) = ( $1, $2 );
	    @resultlist = grep( ! /^${t}:/, @resultlist );
	    push( @resultlist, $chcmd );
	    }
	}
    $newresultstring = join(",",@resultlist);

    if( $cpi_vars::FORM{val0} =~ /,proposed_solution=(\d*)$/ )
	{
	$newsolution = $1;
	$cpi_vars::FORM{val0} =~ s/,proposed_solution=\d*$//;
	}

    &update_solutions( $objnum, $newsolution, $newresultstring );
    }

#########################################################################
#	User has created a new or modified an object.			#
#########################################################################
sub func_update
    {
    my @stack		= split(/\|/,$cpi_vars::FORM{stack});
    %caller		= map { split(/=/) } split(/,/,$stack[$#stack]);

#    print "func_update:<br>",
#	map( " * caller{$_}=\"$caller{$_}\"<br>", keys %caller );

    my $objtype		= $caller{objtype};
    my $objnum		= $caller{objnum};
    my $shortobj	= &formdef("short");
    my $shortcomp	= &justtext($shortobj);
    my $longobj		= &formdef("long");
    my $longcomp	= &justtext($longobj);

#    print "stack= [", join("] [",@stack), "]<br>\n",
#	map( "* caller{$_}=\"$caller{$_}\"<br>\n", sort keys %caller );

    if($shortcomp eq "")
	{push(@problems, "XL(No short description of [[$objtype]] specified.)");}
    else
        {
	if( $objtype eq "result" && $shortobj !~ /:/ )
	    {
	    my $testnum;
	    for( my $ind=$#stack; $ind>=0; $ind-- )
		{
	        if ( $stack[$ind] =~ /objtype=test,objnum=(\d+)/ )
		    {
		    $testnum = $1;
		    last;
		    }
		}
	    $shortobj = &DBDgetdef("test",$testnum,"short") . $RSEP . $shortobj;
	    $shortcomp = &justtext($shortobj);
	    }
	my $testind = &text_to_db_ind( $objtype, $shortcomp );
	push( @problems,
	    "XL(New $objtype [[$shortobj]] already matches $objtype) XL(" .
	        &DBDgetdef($objtype,$testind,"short") . ")" )
		if( $testind ne "" && $testind ne $objnum );
	}
#    if($longcomp eq "")
#        {push(@problems, "XL(No long description of $objtype specified.)" );}
#    else
#	{
#	my $testind = &text_to_db_ind( $objtype, $longcomp );
#	push( @problems,
#	    "XL(New $objtype [[$shortobj]] long description already matches $objtype) XL(" .
#	        &DBDgetdef($objtype,$testind,"short") . ")" )
#		if( $testind ne "" && $testind ne $objnum );
#	}

    return &show_problems("Problems with new $objtype") if( @problems );

    &DBDwrite();
    &DBDput($objtype,($objnum=&DBDget0($objtype))+1) if( $objnum eq "NEW" );
    &DBDchange($objtype,$objnum,"short",$shortobj);
    &DBDchange($objtype,$objnum,"long",$longobj);

    &{ $OBJ_INFO{$objtype}{"update"} }( $objnum )
        if( $OBJ_INFO{$objtype}{"update"} );

    $cpi_vars::FORM{stack} =~
	s/objtype=$objtype,objnum=NEW/objtype=$objtype,objnum=$objnum/g;

    # FIXME
    # Arguably, the following shouldn't need to happen.  This is here
    # for the case when display_case changes something ($cpi_vars::FORM{results})
    # and is creating a NEW object.  The <select> specifies
    # the object number, and in the case of a new object, that value
    # is NEW just as it is in the stack.
    $cpi_vars::FORM{val0} =~
	s/objtype=$objtype,objnum=NEW/objtype=$objtype,objnum=$objnum/g;
    # EOFIXME

    &actual_select(0);
    &DBDpop();
    return "";
    }

#########################################################################
#	Prune out solutions on the bases of tests already executed.	#
#########################################################################
sub review_tests
    {
    my( $casenum, $respertestp, $testlistp ) = @_;
    my $count = 0;
    foreach my $tr ( split(/,/, &DBDgetdef("case",$casenum,"results") ) )
	{
	my( $t, $r ) = split( /:/, $tr );
	#next if( $r < 0 );
	push( @$testlistp, $t ) unless( $respertestp->{$t} );
	${ $respertestp->{$t} }{$r} = 1;
	$count++;
	}
    return $count;
    }

#########################################################################
#	Loop through taken tests to produce viability and plausibilities	#
#########################################################################
sub get_viable_solutions
    {
    my( $viablep, $plausibilityp, $respertestp, $testlistp ) = @_;
    foreach my $t ( @$testlistp )
        {
	my $testname = &DBDget("test",$t,"short");
	if( my @associated = &DBDget("test",$t,"associated") )
	    {
	    my @newviable = ();
	    foreach my $s ( @$viablep )
		{
		my $solname = &DBDget("solution",$s,"short");
		if( (my $total = &DBDget0("solution",$s,$t,"total")) <= 0 )
		    {
		    #$DEBUG && "Solution $s never been tested by $t.<br>\n";
		    }
		else
		    {
		    #print "CMC $testname $solname total=$total.<br>\n";
		    my $numagreedintest = 0;
		    foreach my $r ( @associated )
			{
			my $resname = &DBDget("result",$r,"short");
			my $hadthisresult = &DBDget0("solution",$s,$t,$r);
			my $agreedwiththisresult =
			    ( (${$respertestp->{$t}}{$r})
			    ? $hadthisresult
			    : ($total-$hadthisresult)
			    );
			$numagreedintest += $agreedwiththisresult;
			#print "CMC $testname $solname $resname hadthisresult=$hadthisresult agreedwiththisresult=$agreedwiththisresult.<br>\n";
			}
		    my $agreement = $numagreedintest / $total / scalar(@associated);
		    #print "CMC $testname $solname agreement=$agreement.<br>\n";
		    ${$plausibilityp}[$s] *= $agreement;
		    }
		#print "CMC $testname $solname p=", ${$plausibilityp}[$s], ".<br>\n";
		push( @newviable, $s ) if( ${$plausibilityp}[$s] > $THRESHHOLD )
		}
	    @$viablep = @newviable;
	    }
	}
    }

#########################################################################
#	Add to the list of tests already taken a sorted list of tests	#
#	that will provide maximum differentiation for minimum cost.	#
#########################################################################
sub order_new_tests
    {
    my( $viablep, $respertestp, $testlistp, $tscorep ) = @_;
    for( my $t= &DBDget("test"); $t-- > 0; )
	{
	next if( defined($respertestp->{$t}) );	# Skip test if already done

	my @associated = &DBDget("test",$t,"associated");
	next if( ! @associated );		# Skip test if malformed

	$tscorep->{$t} = 0;

	my @possibilities =
	    ( &DBDget("test",$t,"multiple")
	    ? 0..( (1<<(scalar(@associated))) - 1 )
	    : map( 1<<$_, 0 .. (scalar(@associated)-1) )
	    );

	foreach my $possibility ( @possibilities )
	    {
	    foreach my $s ( @$viablep )
	        {
		if( (my $total = &DBDget0("solution",$s,$t,"total")) <= 0 )
		    {
		    #$DEBUG && "Solution $s never been tested by $t.<br>\n";
		    }
		else
		    {
		    my $tmppossibility = $possibility;
		    my $numagreedintest = 0;
		    foreach my $r ( @associated )
			{
			my $hadthisresult = &DBDget0("solution",$s,$t,$r);
			my $agreedwiththisresult =
			    ( $tmppossibility % 2
			    ? $hadthisresult
			    : ( $total - $hadthisresult )
			    );
			$numagreedintest += $agreedwiththisresult;
			$tmppossibility >>= 1;
			}
		    my $agreement = $numagreedintest / $total / scalar(@associated);
		    my $diff = 1 - $agreement;		# CMC ACK ACK ACK!
		    $tscorep->{$t} += $diff;
		    }
		}
	    }
	}
    push( @$testlistp, sort {$tscorep->{$b} <=> $tscorep->{$a}} keys %$tscorep )
    }

#########################################################################
#	Determine the test suites in the test list.			#
#########################################################################
sub get_order
    {
    my( @testlist ) = @_;
    my $numtests = scalar( @testlist );
    my $numassociated;
    my @associated;
    my @order;
    for( my $t=0; $t<$numtests; )
        {
	my $found = -1;
	for( my $s=&DBDget0("suite"); $found < 0 && $s-->0; )
	    {
	    if( @associated = &DBDget( "suite", $s, "associated" ) )
		{
		$numassociated = scalar(@associated);
		my $i;
		for( $i=0; $i<$numtests && $i<$numassociated; $i++ )
		    {
		    last if( $testlist[$t+$i] != $associated[$i] );
		    }
		$found = $s if( $i == $numassociated );
		}
	    }
	if( $found < 0 )
	    {
	    push( @order, $testlist[$t++] );
	    }
	else
	    {
	    $t += $numassociated;
	    push( @order, "s$found" );
	    }
	}
    return @order;
    }

#########################################################################
#	Return a string with the HTML for the table of tests & results.	#
#########################################################################
sub list_tests
    {
    my( $casenum, $testlistp, $respertestp, $tscorep ) = @_;
    my $pstring = <<EOF;
<tr><th align=right>XL(Score)</th><th align=left>Suite</th><th align=left>XL(Test)</th><th colspan=2 align=left>XL(Results)</th></tr>
EOF

    my $colorind = 0;
    foreach my $sp ( &get_order( @$testlistp ) )
	{
	my @minitestlist;
	my $cursuite;
	if( $sp =~ /s(.*)/ )
	    { @minitestlist = &DBDget("suite",$cursuite=$1,"associated"); }
	else
	    { @minitestlist = $sp; }
	foreach my $t ( @minitestlist )
	    {
	    $pstring .= "<tr><td align=right>" .
		&first_defined( $tscorep->{$t} ) . "</td>";
	    if( ! defined( $cursuite ) )
	        { $pstring .= "<td></td><td>"; }
	    elsif( $cursuite < 0 )
	        { $pstring .= "<td>"; }
	    elsif( $cursuite >= 0 )
	        {
		my @associated = &DBDget("suite",$cursuite,"associated");
		my $nassociated = scalar(@associated);
		my $short = &DBDgetdef("suite",$cursuite,"short");
		$pstring .= <<EOF;
<td align=left rowspan=$nassociated>
<a href='javascript:answer_button("call","dest=display,objtype=suite,objnum=$cursuite");'>
XL($short)</a></td><td>
EOF
		$cursuite = -1;
		}
	    $pstring .= 
		"<a href='javascript:answer_button(\"call\",\"dest=display,objtype=test,objnum=$t\");'>XL(" .
		&DBDget("test",$t,"short") .
		")</a></td><td colspan=2>";
	    my @associated = &DBDget("test",$t,"associated");
	    if( scalar(@associated) == 0 )
		{
		$pstring .= "<div style='background:black;color:yellow'>XL(Test unusable, no results defined yet)</div>";
		}
	    else
		{
		$pstring .= "<select name=changeres onChange='answer_button(\"goto\",\"dest=display,objtype=case,objnum=$casenum\");'>\n";
		my %seenresult = ( -1, 1 );
		%seenresult = %{$respertestp->{$t}} if(defined($respertestp->{$t}));
		my $mult = &DBDget("test",$t,"multiple");
		my @all_positive_results = ();
		foreach my $ans ( -1, @associated )
		    {
		    my $selflag = ( (!$mult && $seenresult{$ans}) ? " selected" : "" );
		    my $anstext = &result_text( $ans );
		    push( @all_positive_results, "XL($anstext)" )
			if( $seenresult{$ans} );
		    if( $ans == -1 || ! $mult )
			{$pstring.="<option$selflag value='$t:$ans'>XL($anstext)\n";}
		    elsif( $seenresult{$ans} )
			{$pstring.="<option$selflag value='-$t:$ans'>XL(Remove) XL($anstext)\n";}
		    else
			{$pstring.="<option$selflag value='+$t:$ans'>XL(Add) XL($anstext)\n";}
		    }
		$pstring .= "<option selected>".join(",",@all_positive_results)
		    if( $mult );
		$pstring .= "</select>";
		}
	    $pstring .= "</td></tr>\n";
	    }
	}
    return $pstring;
    }

#########################################################################
#	Print the various buttons for solving/unsolving the case,	#
#	adding tests, etc.						#
#########################################################################
sub case_disposition
    {
    my( $casenum, $viablep, $plausibilitiesp) = @_;
    my $pstring = "<tr><td></td><th colspan=2>" .
        &button("Run a different test","call","dest=search,objtype=testsuite,select=better_test")
	. "</th><td>";

    my $solution = &DBDgetdef("case",$casenum,"solution");
    my $soltxt = &DBDgetdef("solution",$solution,"short") if( $solution ne "" );
    my $exptxt = "";
    my $buttxt = "";
    my $expsep = "";
    if( ! $soltxt )
        {
	$buttxt = &button("Select or create solution","call",
	    "dest=search,objtype=solution,select=correct_solution");
	}
    else
        {
	$exptxt = "XL(Recorded solution was:) \"XL($soltxt).\"<br>";
	$buttxt =
	    &button("Case no longer solved","goto",
		"dest=display,objtype=case,objnum=$casenum,proposed_solution=")
	    . &button("Select or create different solution","call",
		"dest=search,objtype=solution,select=correct_solution");
	}

    my $great_answer;
    foreach my $ans ( @$viablep )
        {
	if( $plausibilitiesp->[$ans] > 0.85 )
	    {
	    if( defined($great_answer) )
	        { $great_answer = -1; }
	    else
	        { $great_answer = $ans; }
	    }
	elsif( $plausibilitiesp->[$ans] > 0.5 )
	    { $great_answer = -1; }
	}
	    
    if( scalar(@$viablep) == 0 )
        {
	$exptxt .= "XL(Tests indicate no solutions.)";
	}
    elsif( defined($great_answer) && $great_answer >= 0 )
        {
	#my $propsolnum = $viablep->[0];
	my $propsolnum = $great_answer;
	my $propsolution= &DBDget("solution",$propsolnum,"short");
	my $solname = "Indicated solution";
	if( $solution eq "" )
	    {
	    $exptxt .= "XL($solname is) \"XL($propsolution)\".";
	    $buttxt .= &button("$solname is correct","goto",
	        "dest=display,objtype=case,objnum=$casenum,proposed_solution=$propsolnum")
	    }
	elsif( $solution eq $propsolnum )
	    {
	    $exptxt .= "XL(Solution is:) \"XL($propsolution)\".";
	    }
	else
	    {
	    $exptxt .= "XL(but the $solname is:) \"XL($propsolution)\".";
	    $buttxt .= &button("$solname is correct","goto",
	        "dest=display,objtype=case,objnum=$casenum,proposed_solution=$propsolnum");
	    }
	}
    else
	{
	$exptxt .= "XL(Testing indicates "
	    . scalar(@$viablep) . " solutions.)";
	}
    $pstring .= "<tr><td></td><td colspan=2>$exptxt</td><th>$buttxt</th></tr>\n";
    return $pstring;
    }

#########################################################################
#	Print a plausibility table for all of the solutions		#
#########################################################################
sub plausibility_table
    {
    my( $cutoff, $viablep, $plausibilities ) = @_;
    my $toprint = "<tr><th colspan=3 width=50% align=left>XL(Top $cutoff solutions)</th>" .
		    "<th width=25% align=right>XL(Plausibility)</th>" .
    		    "<th width=25% align=right>XL(Probability)</th></tr>\n";
    my $sum = 0;
    grep( $sum+=$plausibilities->[$_], @$viablep );
    foreach my $s ( sort {$plausibilities->[$b]<=>$plausibilities->[$a]} @$viablep )
        {
	last if( $cutoff-- <= 0 );
	$toprint .= "<tr><td colspan=3>XL(" .
	    &DBDget("solution",$s,"short") . ")</td><td align=right>" .
	    sprintf("%5.1f",100*$plausibilities->[$s]) . "%</td><td align=right>" .
	    sprintf("%5.1f",100*$plausibilities->[$s]/$sum) . "%</td></tr>\n";
	}
    return $toprint;
    }

#########################################################################
#	Given the results of tests in $cpi_vars::FORM{casenum},		#
#	find the list of viable solutions that match the criteria.	#
#									#
#	Show all of the tests and their results so the user can change	#
#	them if he has made a mistake.					#
#									#
#	If there are no solutions, he must change his test results or	#
#	create a new solution.						#
#									#
#	If there is only one solution, give him a chance to accept it,	#
#	reject it or create more specific solution for it.		#
#									#
#	If there are multiple solutions, propose some more tests to	#
#	narrow the solutions down further.				#
#########################################################################
sub display_case
    {
    my ( $casenum )	= @_;	# Case we're evaluating
    my @viable		=	# List of solutions tests haven't eliminated
				0 .. ( &DBDgetdef("solution") - 1 );
    my @plausibility	=	# Plausibilities for each of those solutions
				map( 1.0, @viable );
    my %respertest	= ();	# Result array for each test already taken
    my @testlist	= ();	# List of tests taken (in order)
    my %tscore		= ();	# Score of effectiveness of question

    if( $casenum ne "NEW" && &review_tests($casenum, \%respertest, \@testlist) )
	{&get_viable_solutions(\@viable,\@plausibility,\%respertest,\@testlist);}

    #	Note that if a solution hasn't had a particular test its results
    #	result is left at 1.

    #$DEBUG && @viable && print join(" ",map("p$_=$plausibility[$_]",@viable)),"<br>\n";

    &order_new_tests( \@viable, \%respertest, \@testlist, \%tscore )
	if( scalar(@viable) > 1 );

    #$DEBUG && print "testlist=[".join(",",@testlist)."]<br>\n";

    return	&plausibility_table( 5, \@viable, \@plausibility ) .
		&list_tests( $casenum, \@testlist, \%respertest, \%tscore ) .
    		&case_disposition( $casenum, \@viable, \@plausibility );
    }

#########################################################################
#	Work up the object type dependent part of displaying a test.	#
#########################################################################
sub display_test
    {
    my( $objnum ) = @_;
    my $objtype = "test";
    my @associated = ();
    my @enabled = ();
    if( $objnum ne "NEW" )
	{
	@associated = &DBDget($objtype,$objnum,"associated");
	@enabled = &DBDget($objtype,$objnum,"enabled");
	}
    my $pstring .= "<tr><td colspan=5><center>";
    $pstring .= &button("Add possible result","call",

	#If we want to be able to re-use results for different tests, uncomment:
        #"dest=search,objtype=result,select=add_a_new_outcome") .

	#If we want results to be specific to a test, uncomment:
        "dest=display,objtype=result,objnum=NEW,select=add_a_new_outcome") .

	# "&nbsp;&nbsp;&nbsp;&nbsp;" .
	# "<input type=checkbox name=multiple value=checked" .
	# ( &DBDget($objtype,$objnum,"multiple") ? " checked" : "" ) .
	# "> Allow multiple"
	"</center>\n";
    if( ! @associated )
        { $pstring .= "<div style='background:black;color:yellow' align=center>XL(No results defined yet)</div>"; }
    else
	{
	my %enabled = map { $_, 1 } @enabled;
	my $maxlen = 0;
	foreach my $r ( @associated )
	    {
	    $maxlen=$_ if( ($_=length(&result_text($r))) > $maxlen );
	    }
	$maxlen = $maxlen * 8 + 8;
	foreach my $r ( @associated )
	    {
	    my $c = ( $enabled{$r} ? " checked" : "" );
	    my $e = ( $enabled{$r} ? "" : "disabled" );
	    my $txt = &result_text($r);
	    $pstring .= <<EOF
<nobr><input type=checkbox name=enabled$c value=$r
onClick='window.document.answerform.but$r.disabled=!this.checked;'
><input type=button name=but$r$e value='XL($txt)'
 style='font-family:Courier New;font-size:8px;width:${maxlen}px;text-align:left'
onClick='answer_button("call","dest=display,objtype=result,objnum=$r");'></nobr>
EOF
	    }
	}
    $pstring .= "</td></tr>\n";
    return $pstring;
    }

#########################################################################
#	Work up the object type dependent part of displaying a suite.	#
#########################################################################
sub display_suite
    {
    my( $objnum ) = @_;
    my $objtype = "suite";
    my @associated = ();
    my @enabled = ();
    if( $objnum ne "NEW" )
	{
	@associated = &DBDget($objtype,$objnum,"associated");
	@enabled = &DBDget($objtype,$objnum,"enabled");
	}
    my $pstring .= "<tr><td colspan=4><center>";
    $pstring .= &button("Add associated test","call",

	#If we want to be able to re-use tests for different results, uncomment:
        "dest=search,objtype=test,select=add_a_new_test") .

	#If we want tests to be specific to a suite, uncomment:
        #"dest=display,objtype=test,objnum=NEW,select=add_a_new_test") .
	"</center>\n";

    if( ! @associated )
        { $pstring .= "<div style='background:black;color:yellow' align=center>XL(No associated tests yet)</div>"; }
    else
	{
	my %enabled = map { $_, 1 } @enabled;
	my $maxlen = 0;
	foreach my $t ( @associated )
	    {
	    $maxlen=$_ if( ($_=length(&DBDgetdef("test",$t,"short"))) > $maxlen );
	    }
	$maxlen = $maxlen * 8 + 8;
	foreach my $t ( @associated )
	    {
	    my $c = ( $enabled{$t} ? " checked" : "" );
	    my $e = ( $enabled{$t} ? "" : "disabled" );
	    my $txt = &DBDgetdef("test",$t,"short");
	    $pstring .= <<EOF
<nobr><input type=checkbox name=enabled$c value=$t
onClick='window.document.answerform.but$t.disabled=!this.checked;'
><input type=button name=but$t$e value='XL($txt)'
 style='font-family:Courier New;font-size:8px;width:${maxlen}px;text-align:left'
onClick='answer_button("call","dest=display,objtype=test,objnum=$t");'></nobr>
EOF
	    }
	}
    $pstring .= "</td></tr>\n";
    return $pstring;
    }

#########################################################################
#	User is entering a new or modifying an object.			#
#########################################################################
sub func_display
    {
    my $objtype		= $caller{objtype};
    my $objnum		= $caller{objnum};
    my $shortobj	= "";
    my $longobj		= "";
    my $owner		= "";

    if( $objnum ne "NEW" )
        {
	$shortobj	= &DBDget($objtype,$objnum,"short");
	$longobj	= &DBDget($objtype,$objnum,"long");
	$owner		= &DBDget($objtype,$objnum,"owner");
	}
    elsif( $objtype eq "case" )
        {
	$shortobj	= "$cpi_vars::USER-".time();
	$longobj	= "${shortobj}:";
	$owner		= $cpi_vars::USER;
	}

    $shortobj = $2 if( $objtype eq "result" && $shortobj =~ /^.*?$RSEP(.*)$/ );

    $_ = &safe_html( $shortobj );
    my $pstring = &setup_form("answer","return","stack",
        "val0=","update=1","discipline=$discipline") . <<EOF;
<center><table bgcolor=$OBJ_INFO{$objtype}{base} border=1>
<tr><td colspan=3 width=50%><b>XL(Enter short name of $objtype ${objnum}:)</b></td>
    <th width=50% align=left colspan=2><input type=text name=short value="$_">
EOF
    $pstring .= "XL(Owned by [[$owner]])" if( $owner ne "" );
    $pstring .= "</th></tr>\n";
    $pstring .= &{$OBJ_INFO{$objtype}{"display"}}( $objnum )
    	if( $OBJ_INFO{$objtype}{"display"} );
    $pstring .= <<EOF;
<tr><td colspan=5><b>XL(Enter long description of $objtype):</b><br><center>
    <textarea name=long rows=10 cols=70>$longobj</textarea>
    </center></td></tr>
EOF
    
    my @stack = split(/\|/,&formdef("stack"));
    my %callercaller = map { split(/=/) } split(/,/,$stack[$#stack-1]);
    my $updtxt = "Update";
    if( my $prevtype = $callercaller{objtype} )
        {
	$updtxt .= " and return to $prevtype";
	$updtxt .= " $callercaller{dest}" if($callercaller{dest} ne "display");
	}
    else
        { $updtxt .= " and return to showing the database"; }
    $pstring .= "<tr><th colspan=5>" . &button($updtxt,"return") . <<EOF;
</th></tr>
</table></center></form>
EOF
    return $pstring;
    }

my %cache = ();
#########################################################################
#	Return a list of the object type in the "natural" order.	#
#########################################################################
sub sort_objs
    {
    my( $objtype ) = @_;
    $cache{$objtype} || return ();
    if( $objtype eq "result" )
        {
	my @testscores;
	for( my $t=$cache{test}; $t-->0; )
	    {
	    grep( $testscores[$_]=($testscores[$_]||0)+1,
		&DBDget("test",$t,"associated") );
	    }
	@{$cache{testscores}} = @testscores;
	return (sort {$testscores[$a]<=>$testscores[$b]} 0..($cache{result}-1))
	}
    return 0 .. ($cache{$objtype}-1);
    }

#########################################################################
#	Return only the last part of the line for a show of tests.	#
#########################################################################
sub table_test
    {
    my( $o, $bgcolor ) = @_;
    my $objtype = "test";
    my @associated = &DBDget($objtype,$o,"associated");
    my %enabled = map { $_, 1 } &DBDget($objtype,$o,"enabled");

    my @rescore = ();
    my $rows = 0;
    my $pstring = "";
    foreach my $r ( @associated )
	{
	$rescore[$r] = 0;
	for( my $s=$cache{solution}; $s-- >0; )
	    { $rescore[$r] += &DBDget0("solution",$s,$o,$r); }
	}
    foreach my $r ( sort {$rescore[$b]<=>$rescore[$a]} @associated )
	{
	my $rtext = &result_text($r);
	$pstring .=
	    ( $pstring ? "<tr bgcolor=$bgcolor><td>" : "<td>" ) .
	    ( $enabled{$r} ? "" : "<strike>" ) .
	    "XL($rtext)" .
	    ( $enabled{$r} ? "" : "</strike>" ) .
	    "</td><td>";
	foreach my $s ( sort
	    {
	    &DBDget0("solution",$b,$o,$r)
		<=>
	    &DBDget0("solution",$a,$o,$r)
	    } 0 .. ($cache{solution}-1) )
	    {
	    my $rv = &DBDget("solution",$s,$o,$r);
	    $pstring .= " XL(". &DBDget("solution",$s,"short") . ")=$rv"
		if( $rv );
	    }
	$pstring .= "</td><td align=right>$rescore[$r]</td></tr>\n";
	$rows++;
	}
    return ( <<EOF, $rows, "<td rowspan=$rows></td>$pstring" );
    <th></th>
    <th align=left>XL(Results)</th>
    <th align=left>XL(Counts)</th>
    <th align=right>XL(Total)</th>
EOF
    }

#########################################################################
#	Return only the last part of the line for a show of suites.	#
#########################################################################
sub table_suite
    {
    my( $o, $bgcolor ) = @_;
    my $objtype = "suite";
    my @associated = &DBDget($objtype,$o,"associated");
    my %enabled = map { $_, 1 } &DBDget($objtype,$o,"enabled");
    my $rows = 0;
    my $pstring = "";
    foreach my $t ( @associated )
	{
	$pstring .=
	    ( $pstring ? "<tr bgcolor=$bgcolor><td>" : "<td>" ) .
	    ( $enabled{$t} ? "" : "<strike>" ) .
	    "XL(" . &DBDgetdef( "test", $t, "short" ) . ")" .
	    ( $enabled{$t} ? "" : "</strike>" ) .
	    "</td><td></td><td></td></tr>\n";
	$rows++;
	}
    return ( <<EOF, $rows, "<td rowspan=$rows></td>$pstring" );
    <th></th>
    <th>XL(Tests)</th>
    <th></th>
    <th></th>
EOF
    }

#########################################################################
#	Return only the last part of the line for a show of results.	#
#########################################################################
sub table_result
    {
    my( $o, $bgcolor ) = @_;
    return ( "<th>XL(Uses)</th>", 1, <<EOF0 );
<td valign=top align=right>$cache{testscores}[$o]</td></tr>
EOF0
    }

#########################################################################
#	Return only the last part of the line for a show of solutions.	#
#########################################################################
sub table_solution
    {
    my( $o, $bgcolor ) = @_;
    my $objtype = "solution";
    my @caselist = &DBDget($objtype,$o,"cases");
    my $ncases = scalar(@caselist);
    print "TS($o) returns [", join(",",@caselist), "] nc=$ncases.<br>\n";
    my $rows = 0;
    my $pstring = "";
    for( my $t=$cache{test}; $t-- > 0; )
	{
	if( (my $total = &DBDget0("solution",$o,$t,"total")) > 0 )
	    {
	    $rows++;
	    $pstring .= "<tr bgcolor=$bgcolor>" if( $pstring );
	    $pstring .= "<td valign=top>";
	    my @associated = &DBDget("test",$t,"associated");
	    my $lastr = scalar( @associated ) - 1;
	    my %scores;
	    grep( $scores{$_}=($scores{$_}||0)
		+ &DBDget("solution",$o,$t,$_), @associated );
	    $pstring .= "XL(" . &DBDget("test",$t,"short") . ")</td>" .
		"<td valign=top>";
	    my $total = 0;
	    my $count = 0;
	    foreach my $r ( sort {$scores{$b}<=>$scores{$a}} @associated )
		{
		$pstring .= "&nbsp;" if( $count++ > 0 );
		$pstring .= "XL(" . &result_text($r) . ")=$scores{$r}\n";
		$total += $scores{$r};
		}
	    $pstring .= "</td><td valign=top align=right>$total</td></tr>\n";
	    }
	}
    return ( <<EOF0, $rows, <<EOF1 );
    <th>#</th>
    <th align=left>XL(Test)</th>
    <th align=left>XL(Results)</th>
    <th align=right>XL(Total)</th>
EOF0
    <td valign=top align=right rowspan=$rows>$ncases</td>$pstring
EOF1
    }

#########################################################################
#	Return only the last part of the line for a show of case.	#
#########################################################################
sub table_case
    {
    my( $o, $bgcolor ) = @_;
    my $objtype = "case";
    my $solnum = &DBDgetdef($objtype,$o,"solution");
    my %resultof = ();
    my @origorder = ();
    my $soltxt .=
        ( $solnum eq ""
	? "<th colspan=3>XL(In progress)</th></tr>\n"
	: "<th align=left colspan=2>XL(Solution)</th><th align=left>XL(" .
	    &DBDgetdef("solution",$solnum,"short") . ")</th></tr>\n" );

    foreach my $tr ( split(/,/,&DBDgetdef($objtype,$o,"results") ) )
        {
	my( $t, $r ) = split(/:/,$tr);
	push( @origorder, $t );
	$resultof{ $t } = &result_text($r);
	}

    my $rows = 1;
    foreach my $sp ( &get_order( @origorder ) )
        {
	my @minilist = ();
	if( $sp !~ /s(\d)/ )
	    { @minilist = ( $sp ); }
	else
	    {
	    @minilist = &DBDget( "suite", $1, "associated" );
	    $soltxt .=
		"<tr bgcolor=$bgcolor><td colspan=3 align=center>XL(" .
		&DBDget( "suite", $1, "short" ) .
		"):</td></tr>\n";
	    $rows++;
	    }
	    
	foreach my $t ( @minilist )
	    {
	    $soltxt .=
	    	"<tr bgcolor=$bgcolor><td colspan=2 align=left>XL(" .
		&DBDgetdef("test",$t,"short") .
		")</td>" .
		"<td>$resultof{$t}</td></tr>\n";
	    $rows++;
	    }
	}
    return ( <<EOF0, $rows, "<td valign=top rowspan=$rows>" . &DBDgetdef($objtype,$o,"owner") . <<EOF1 );
    <th>XL(Owner)</th>
    <th colspan=2>XL(Test)</th>
    <th>XL(Results)</th>
EOF0
</td>$soltxt
EOF1
    }

#########################################################################
#	Print all objects that match the supplied regular expression.	#
#########################################################################
sub table_entries
    {
    my( $objtype, $expr ) = @_;
    my $pstring = "";
    my $newfunc = ( $caller{select} ? "goto" : "call" );
    my $newdest = ( $caller{select} ? "select" : "display" );
    my $colorind = 0;
    if( $expr ne "" )
	{
	foreach my $cobjtype ( @OBJECT_TYPES )
	    {
	    defined($cache{$cobjtype}) || ($cache{$cobjtype} = &DBDget($cobjtype));
	    }
	my $found = 0;
	my $ucf = ucfirst $objtype;

	foreach my $o ( &sort_objs($objtype) )
	    {
	    my $bgcolor = $OBJ_INFO{$objtype}{rows}[ ++$colorind%2 ];
	    my $short;
	    if( $objtype eq "result" )
	        { $short = &result_text($o); }
	    else
	        { $short = &DBDgetdef($objtype,$o,"short"); }
	    my $long = &DBDgetdef($objtype,$o,"long");
	    my ( $resthdr, $rows, $rest ) =
		( $OBJ_INFO{$objtype}{"table"}
		?  &{$OBJ_INFO{$objtype}{"table"}}($o,$bgcolor)
		: ( "problem", 1, "</tr>" )
		);
	    next if( ($short.$long.$rest) !~ /$expr/i );
	    $pstring .= ( <<EOF0 . $resthdr . "</tr>\n" ) unless( $found );
<tr><th colspan=7><font size=+2 color=white>XL(${ucf}s)</font></th></tr>
<tr><th align=right>XL(Select)</th>
<th align=left>XL(Brief)</th>
<th align=left>XL(Long description)</th>
EOF0
	    $pstring .= <<EOF1 . &button($o,$newfunc,"dest=$newdest,objtype=$objtype,objnum=$o") . <<EOF2;
<tr bgcolor=$bgcolor>
<th valign=top align=right rowspan=$rows>
EOF1
</th><th valign=top align=left rowspan=$rows>XL($short)</th>
<td valign=top rowspan=$rows>XL($long)</td>$rest
EOF2
	    $found++;
	    }
	$pstring .= "<tr><th colspan=7 bgcolor=$NOTFOUND>XL(No ${objtype}s found)</th></tr>\n" unless($found);
	}
    $pstring .= "<tr><th colspan=7 align=left>" .
	&button("Create new $objtype",$newfunc,"dest=display,objtype=$objtype,objnum=NEW") .
	"</th></tr>\n";		# if( $objtype eq "case" );
    return $pstring;
    }

#########################################################################
#	Allow user to search through tests with a regular expression.	#
#########################################################################
my %search_header =
    (
    "add_a_new_outcome"	=> "Select a new possible test outcome or create one",
    "better_test"	=> "Select a better test to run or create one",
    "correct_solution"	=> "Select correct solution or create one",
    "add_a_new_test"	=> "Select a test to include in the suite"
    );
sub func_search
    {
    my $objtype = $caller{objtype};
    my $selflag = "";
    my $msg = "Select a $objtype to display or modify";
    if( $_ = $caller{select} )
        {
	$selflag = ",select=$_";
	$msg = $search_header{$_} if( $search_header{$_} );
	}

    my $tosearch = &formdef("search");
    $tosearch = ( ($objtype eq "Xcase") ? $cpi_vars::USER : "." )
	if( $tosearch eq "" );
    my $objtxt = ( $objtype eq "all" ? "database" : "${objtype}s" );
    my $pstring = &setup_form("answer","goto","stack",
        "val0=dest=search,objtype=$objtype$selflag","discipline=$discipline")
	. <<EOF;
<center><table bgcolor=$OBJ_INFO{$objtype}{base} border=1>
EOF
    $pstring .= "<tr><th colspan=7>XL($msg)</th></tr>\n" if( $msg );
    $_ = &safe_html( $tosearch );
    $pstring .= <<EOF
<tr><th align=left colspan=3 width=50% nowrap>XL(Search $objtxt with string):</th>
    <td align=right colspan=4 width=50% nowrap>
        <input type=text name=search value="$_">
EOF
	. &button("Search","goto","dest=search,objtype=$objtype$selflag") .
	"</td></tr>";
    my @typestosearch =
        ( $objtype eq "all"		? @OBJECT_TYPES		:
	( $objtype eq "testsuite"	? ("suite","test")	:
	( $objtype ) ) );
    foreach my $objtype ( @typestosearch )
	{ $pstring .= &table_entries($objtype,$tosearch); }
    $pstring .= "</table></center></form>\n";
    return ( $pstring );
    }

#########################################################################
#	Debug routine:  Dump the entire database by searching for "."	#
#	in all databases.						#
#########################################################################
sub func_show_db
    {
    return
        &setup_form("answer","show_db","stack",
	    "val0=","discipline=$discipline") .
        "<center><table $cpi_vars::TABLE_TAGS border=1>" .
        join("", map( &table_entries($_,"."), @OBJECT_TYPES ) ) .
        "</table></center></form>";
    }

#########################################################################
#	Push the specified arguments onto the stack and call the	#
#	appropriate routine.						#
#########################################################################
sub func_call
    {
    my( $pushstack ) = @_;
    my( $callingargs ) = &formdef("val0");
    #print "pushstack=$pushstack callingargs=[$callingargs]<br>\n";
    %caller = map { split(/=/) } split(/,/,$callingargs);
    my @stack = split(/\|/,&formdef("stack"));
    pop( @stack ) unless( $pushstack );
    push(@stack,$callingargs);
    $cpi_vars::FORM{stack} = join("|",@stack);
    $_ = $caller{dest};
    return
	(
	$_ eq "display"		&&	&func_display()		or
	$_ eq "search"		&&	&func_search()		or
	$_ eq "show_db"		&&	&func_show_db()		or
	$_ eq "select"		&&	&func_select()		or
	"FATAL ERROR, caller dest is [$_].<br>"
	);
    }

#########################################################################
#	Pull the last entry off the stack and call the appropriate.	#
#########################################################################
sub func_return
    {
    my( @stack ) = split(/\|/,&formdef("stack"));
    pop( @stack );
    %caller = map { split(/=/) } split(/,/,$stack[$#stack]);
    $cpi_vars::FORM{stack} = join("|",@stack);
    $_ = $caller{dest};
    return
	(
        $_ eq "display"		&&	&func_display()		or
	$_ eq "search"		&&	&func_search()		or
	$_ eq "show_db"		&&	&func_show_db()		or
	"FATAL ERROR in return, dest was [$_].<br>"
	);
    }

#########################################################################
#	User has selected something for something else.  Figure out	#
#	what object needs to be associated with which.			#
#########################################################################
sub func_select
    {
    &actual_select(1);
    return &func_return();
    }

#########################################################################
#	If nothing else to display, display this.			#
#########################################################################
sub default_display
    {
    $cpi_vars::FORM{val0}="dest=search,objtype=case";
    return &func_call(1);
    }

#########################################################################
#	Parse data from ASCII database format				#
#########################################################################
my %VERBMAP = ( "possibly"=>"result", "subtest"=>"test", "reference"=>"case" );
sub parse_ascii_data
    {
    my( $newdata ) = @_;
    my $long;
    my $objtype;
    my $objnum;
    my $lasttest;
    my $lastsuite;
    my $refsolution;
    my $numdefs = 0;
    &DBDwrite();
    foreach my $line ( split(/\n/gs,$newdata) )
        {
	$line =~ s/#.*//;
	$line =~ s/^\s+//g;
	$line =~ s/\s+$//g;
	my @toks = split(/\s+/,$line);
	my $verb = $toks[0];
	my $rest = join(" ",@toks[1..$#toks]);
	if( grep( $verb eq uc($_), @OBJECT_TYPES, keys %VERBMAP ) )
	    {
	    if( defined($refsolution) )
	        {
		&update_solutions( $objnum, $refsolution,
		    &DBDget( $objtype, $objnum, "results" ) );
		undef $refsolution;
		}
	    $verb = lc( $verb );
	    $objtype = ( $VERBMAP{$verb} ? $VERBMAP{$verb} : $verb );

	    if( $rest eq "" )
	        {
		push( @problems,
		    "XL(Empty [[\"",uc($objtype),"\"]] definition.)" );
		undef $long;
		}
	    else
	        {
		if( $objtype eq "result" && $rest !~ /$RSEP/ )
		    { $rest = &DBDget("test",$lasttest,"short") . $RSEP . $rest; }
		my $t = &justtext($rest);
		$objnum = &text_to_db_ind($objtype,$t);
		#print "verb=[$verb] objtype=[$objtype] t=[$t] objnum=[$objnum] rest=[$rest]<br>\n";
		if($objnum ne "" && $objtype ne "result" && $objtype ne "test")
		    {
		    push( @problems,
			"XL($objtype) \"XL($rest)\" XL(is already defined.)");
		    undef $long;
		    }
		else
		    {
		    if( $objnum eq "" )
			{
			&DBDput($objtype,($objnum=&DBDget0($objtype))+1);
			&DBDput($objtype,$objnum,"short",$rest);
			$numdefs++;
			if( $verb ne "reference" )
			    { &DBDput($objtype,$objnum,"long",$rest); }
			else
			    {
			    $refsolution = &DBDget0("solution");
			    &DBDput($objtype,$objnum,"long","Seed case");
			    &DBDput("solution",$refsolution+1);
			    &DBDput("solution",$refsolution,"short",$rest);
			    &DBDput("solution",$refsolution,"long",$rest);
			    }
			}
		    $long = "";

		    if( $verb eq $objtype )
		        { undef $lasttest; undef $lastsuite; }

		    if( $objtype eq "suite" )
		        { $lastsuite = $objnum; }
		    elsif( $objtype eq "test" )
		        { $lasttest = $objnum; }

		    if( $objtype ne $verb )
			{
			if( $objtype eq "test" && defined( $lastsuite ) )
			    {
			    &DBDadd($PARENTS{$objtype},$lastsuite,"associated",$objnum);
			    &DBDadd($PARENTS{$objtype},$lastsuite,"enabled",$objnum);
			    }
			elsif( $objtype eq "result" && defined( $lasttest ) )
			    {
			    &DBDadd($PARENTS{$objtype},$lasttest,"associated",$objnum);
			    &DBDadd($PARENTS{$objtype},$lasttest,"enabled",$objnum);
			    }
			elsif( $objtype ne "case" )
			    {
			    push( @problems,
				"XL($objtype) \"XL($rest)\" XL(not associated with a test.)");
			    }
			}
		    }
		}
	    }
	elsif( $verb eq "MULTIPLE" )
	    {
	    &DBDput($objtype,$objnum,"multiple","checked");
	    }
	elsif( $verb eq "TESTRESULT" )
	    {
	    my( $t, $r ) = split(/ WAS /,$rest);
	    if( $r eq "" )
	        {push(@problems,"XL(Malformed TESTRESULT)");}
	    else
	        {
		my $tind = &text_to_db_ind( "test", &justtext($t) );
		push(@problems,"XL(Cannot find test for [[\"$t\"]].)")
		    if( $tind eq ""  );
		foreach my $rpiece ( split(/,\s*/,$r) )
		    {
		    $rpiece = $t . $RSEP . $rpiece if( $rpiece !~ /$RSEP/ );
		    my $rind = &text_to_db_ind( "result", &justtext($rpiece) );
		    $rind = &text_to_db_ind("result",&justtext("$t$RSEP$rpiece") )
			if( $rind eq "" );
		    if( $rind eq "" )
		        {
			push(@problems,"XL(Cannot find result for [[\"$rpiece\"]].)");
		        }
		    elsif( $tind ne "" )
			{
			my $res = &DBDgetdef($objtype,$objnum,"results");
			$res .= "," if( $res ne "" );
			$res .= "${tind}:${rind}";
			&DBDput($objtype,$objnum,"results",$res);
			}
		    }
		}
	    }
	elsif( $verb eq "CONCLUSION" )
	    {
	    my $sind = &text_to_db_ind("solution",&justtext($rest));
	    if( $sind eq "" )
	        {
		push(@problems,
		    "XL(Cannot find solution for CONCLUSION) $rest");
		}
	    else
		{
		&update_solutions( $objnum, $sind,
		    &DBDget( $objtype, $objnum, "results" ) );
		}
	    }
	elsif( defined($long) )
	    {
	    if( $line =~ /^\s*$/ )
		{ $long .= "\n"; }
	    elsif( $line =~ /^\s*(.*)/ )
		{
		$long .= "$1\n";
		if( defined($refsolution) )
		    { &DBDput("solution",$refsolution,"long",$long); }
		else
		    { &DBDput($objtype,$objnum,"long",$long); }
		}
	    }
	}

    &update_solutions( $objnum, $refsolution,
	&DBDget( $objtype, $objnum, "results" ) )
	    if( defined($refsolution) );

    &DBDpop();
    return $numdefs;
    }

#########################################################################
#	Parse ascii text definitions from web.				#
#########################################################################
sub func_got_upload
    {
    my $numdefs = &parse_ascii_data( &formdef("upload_data") );
    my $pstring = "<h2 align=center>XL($numdefs objects defined.)</h2>";
    $pstring .= &show_problems("Problems with uploaded data")
	if( @problems );
    return $pstring;
    }

#########################################################################
#	Parse ascii text definitions from web.				#
#########################################################################
sub file_upload
    {
    my( $fn, $newdiscipline ) = @_;
    &fatal("read requires a file name.") if( ! defined($fn) );
    &fatal("No discipline specified.") if( ! defined($newdiscipline) );
    my $oldpgraph = $/;
    undef $/;
    open( INF, $fn ) || &fatal("read cannot read ${fn}:  $!");
    $_ = <INF>;
    close( INF );
    $/ = $oldpgraph;

    $discipline = $newdiscipline;
    my $numdefs = &parse_ascii_data( $_ );
    print "$numdefs objects defined.\n";
    &fatal( join("\n",@problems,"") ) if( @problems );
    &cleanup();
    }

#########################################################################
#########################################################################
sub func_get_upload
    {
    return &setup_form("answer","got_upload","discipline=$discipline") . <<EOF;
<center><table border=1>
<tr><th>XL(Name of local file to upload:)</th>
<td><input type=file name=upload_data></td></tr>
<tr><th colspan=2><input type=submit value="XL(Upload)"></th></tr>
</table></center></form>
EOF
    }

my @printarray = ();
my %depending = ();
#########################################################################
#########################################################################
sub download_recurse
    {
    my( $objtype, $childtype, $verb, $objnum, $spacing ) = @_;
    push( @printarray, "$spacing    MULTIPLE\n" )
	if( &DBDget($objtype,$objnum,"multiple" ) );
    my %enabled= map { $_, 1 } &DBDget($objtype,$objnum,"enabled");
    foreach my $c ( sort { $a <=> $b } &DBDget($objtype,$objnum,"associated") )
	{
	push( @printarray, "$spacing    $verb ",
	    &xl( &DBDget($childtype,$c,"short") ),
	    "\n" );
	&download_generic( "", "$spacing    ", $childtype, $c )
	    if( $depending{$childtype}{$c} == 1 );
	}
    }

sub download_test  { &download_recurse( "test",  "result", "POSSIBLY", @_ ); }
sub download_suite { &download_recurse( "suite", "test",   "SUBTEST",  @_ ); }

#########################################################################
#########################################################################
sub download_case
    {
    my( $objnum, $spacing ) = @_;
    my $objtype = "case";
    foreach my $tr (split(/,/,&DBDgetdef($objtype,$objnum,"results")))
	{
	my( $t, $r ) = split(/:/,$tr);
	push( @printarray, "$spacing    TESTRESULT ",
	    &DBDgetdef("test",$t,"short"), " WAS ", &result_text($r), "\n" );
	}
    my $s = &DBDgetdef($objtype,$objnum,"solution");
    push( @printarray, "$spacing    CONCLUSION ",
	&DBDgetdef("solution",$s,"short"),
	"\n" ) if( $s ne "" );
    }

#########################################################################
#########################################################################
sub seed_case_of
    {
    my( $objnum ) = @_;
    my $objtype = "solution";
    foreach my $c ( &DBDgetdef($objtype,$objnum,"cases") )
        {
	return $c if( &DBDgetdef("case",$c,"long") eq "Seed case" );
	}
    return undef;
    }

#########################################################################
#########################################################################
sub download_solution
    {
    my( $objnum, $spacing ) = @_;
    my $objtype = "solution";
    my $c = &seed_case_of( $objnum );
    if( defined( $c ) )
	{
	foreach my $tr (split(/,/,&DBDgetdef("case",$c,"results")))
	    {
	    my( $t, $r ) = split(/:/,$tr);
	    push( @printarray, "$spacing    TESTRESULT ",
		&DBDgetdef("test",$t,"short"), " WAS ", &result_text($r), "\n" );
	    }
	}
    }

#########################################################################
#########################################################################
sub download_generic
    {
    my( $msg, $spacing, $objtype, @objlist ) = @_;
    if( @objlist )
	{
	push( @printarray, "\n", $spacing, $msg, "\n" ) if( $msg );
	foreach my $objnum ( @objlist )
	    {
	    push( @printarray, "\n",
		( $objtype eq "solution" && defined(seed_case_of($objnum))
		? "REFERENCE"
		: uc($objtype)
		),
		" ",
		&xl(&DBDget($objtype,$objnum,"short")),"\n")
		    if( $spacing eq "" );
	    my $long = &DBDgetdef($objtype,$objnum,"long");
	    push(@printarray,"$spacing    ",join("\n$spacing    ",
		split(/\n/gs,$long)),"\n") if( $long ne "" );
	    &{$OBJ_INFO{$objtype}{"download"}}($objnum,"$spacing    ")
		if( $OBJ_INFO{$objtype}{"download"} );
	    }
	}
    }

#########################################################################
#	Produce a text readable (vs. perl-object) version of database.	#
#########################################################################
sub check_if_app_needs_header() { return $cpi_vars::FORM{func} ne "download"; }
sub download
    {
    @printarray =
	("# $discipline database dump of ", scalar localtime(time), ":\n");

    foreach my $objtype ( @OBJECT_TYPES )
	{
	defined($cache{$objtype}) || ($cache{$objtype} = &DBDget($objtype));
	}

    foreach my $objtype ( @OBJECT_TYPES )
        {
	if( $PARENTS{$objtype} )
	    {
	    my $parent = $PARENTS{$objtype};
	    for( my $p=$cache{$parent}; $p-- >0; )
		{
		foreach my $c ( &DBDget($parent,$p,"associated") )
		    { $depending{$objtype}{$c}++; }
		}

	    my @strays = ();
	    my @multiuses = ();
	    for( my $c=0; $c<$cache{$objtype}; $c++ )
		{
		if( $depending{$objtype}{$c} < 1 )
		    { push(@strays,$c); }
		elsif( $depending{$objtype}{$c} > 1 )
		    { push(@multiuses,$c); }
		}

	    &download_generic( "# ".ucfirst(${objtype})."s used in multiple $PARENTS{$objtype}s:", "", $objtype, @multiuses );
	    &download_generic( "# ".ucfirst(${objtype})."s not used in any $PARENTS{$objtype}s:", "", $objtype, @strays );
	    }
	elsif( $cache{$objtype} )
	    {
	    my @todo;
	    if( $objtype eq "solution" )
	        {
		my @reflist = ();
		my @sollist = ();
		foreach my $s ( 0 .. $cache{$objtype} - 1 )
		    {
		    if( defined( &seed_case_of($s) ) )
		        { push( @reflist, $s ); }
		    else
		        { push( @todo, $s ); }
		    }
		&download_generic( "# Seed cases", "", $objtype, @reflist );
		}
	    else
		{
	        foreach my $c ( 0 .. $cache{$objtype} - 1 )
		    {
		    push(@todo,$c)
			if(&DBDgetdef($objtype,$c,"long") ne "Seed case");
		    }
		}
	    &download_generic("# ".ucfirst($objtype)."s:", "", $objtype, @todo)
	        if( @todo );
	    }
	}
    print "Content-type:  text/diagnosis\n\n", @printarray;
    &cleanup();
    }

#########################################################################
#	Mainline							#
#########################################################################
&file_upload( $ARGV[1], $ARGV[2] ) if( !$ENV{SCRIPT_NAME} && $ARGV[0] eq "read" );

&fatal(<<EOF)
XL(Usage):  $cpi_vars::PROG.cgi (dump|dumpaccounts|dumptranslations|undump|undumpaccounts|undumptranslations) [ dumpname ]
    XL(or)
XL(Usage):  $cpi_vars::PROG.cgi read filename discipline
EOF
    if( $ENV{SCRIPT_NAME} eq "" );

#my $bestg = "administrators";
#if( $bestg )
#    { $cpi_vars::FORM{current_group} = $bestg; }
#else
#    { &fatal("No group appropriate for $cpi_vars::REALUSER"); }

my $fn = &formdef("func");
$discipline = $cpi_vars::FORM{discipline};

&download() if( $fn eq "download" );

print "<body $cpi_vars::BODY_TAGS>";

#&show_vars("Form values for \"$fn\":",@DUMP_EXCLUDE);

if( $discipline && &can_admin() )
    {
    my @disclist = &dbget($cpi_vars::DB,"Disciplines");
    &DBDwrite();
    &dbadd($cpi_vars::DB,"Disciplines",$discipline) 
	unless( grep($discipline eq $_,@disclist) );
    &DBDpop();
    }

&xprint
    (
    &formdef("update")		&& &func_update()			or
    $fn eq ""			&& &default_display()			or
    $fn eq "dologin"		&& &default_display()			or
    $fn eq "call"		&& &func_call(1)			or
    $fn eq "goto"		&& &func_call(0)			or
    $fn eq "return"		&& &func_return()			or
    $fn eq "select"		&& &func_select()			or
    $fn eq "show_db"		&& &func_show_db()			or
    $fn eq "got_upload"		&& &func_got_upload()			or
    $fn eq "upload"		&& &func_get_upload()			or
    $fn eq "download"		&& &download()				or
    "Fatal error:  undefined function [$fn]<br>"
    ) if( $discipline );

&footer();

&cleanup(0);
